"""Self-service merchant onboarding: create a merchant + membership +
onboarding submission for a freshly-signed-up Supabase Auth user, register
uploaded compliance documents, resolve onboarding status, and (super-admin
side) review submissions.

`onboarding_submissions.review_status` is a separate lifecycle from
`merchants.status`/`kyc_status` — see supabase/migrations/
20260815090000_onboarding.sql for why. Approving a submission promotes both;
rejecting/requesting more info touches only the submission, so the merchant
stays exactly as they were (still `pending`/`unverified`) while they fix and
resubmit.
"""

import mimetypes
import uuid
from typing import Any

from fastapi import UploadFile
from storage3.utils import StorageException
from supabase import Client

from app.config import get_settings
from app.core.errors import ConflictError, NotFoundError, ValidationAPIError
from app.core.time import utc_now_iso
from app.schemas.auth import AuthenticatedUser
from app.schemas.enums import AccountStatus, DocumentType
from app.schemas.onboarding import OnboardingMerchantAccountCreate
from app.schemas.withdrawals import PricingRuleCreate
from app.services.audit import write_audit_log
from app.services.crud import get_by_id, insert_row, update_row
from app.services.email import (
    send_merchant_welcome_email,
    send_new_merchant_signup_notification_email,
)
from app.services.ledger import get_wallet_balance
from app.services.merchant_code import generate_merchant_code

# Required for a merchant to go live — checked at approval time, not at
# submission, since documents upload separately via
# POST /v1/onboarding/documents. BUSINESS_LICENCE is deliberately excluded:
# the business made it optional everywhere (see DocumentType/the onboarding
# form) so a sole proprietor without one can still get approved.
_REQUIRED_APPROVAL_DOCUMENTS = (DocumentType.NIDA, DocumentType.TIN_CERTIFICATE)

_ALLOWED_DOCUMENT_MIME_TYPES = {"application/pdf", "image/jpeg", "image/png"}
_BUCKET = "merchant-documents"

_ONBOARDED_STATUSES = (AccountStatus.PENDING_VERIFICATION.value, AccountStatus.VERIFIED.value)
_RESUBMITTABLE_STATUSES = (AccountStatus.REJECTED.value, AccountStatus.INFO_REQUESTED.value)


def _find_active_membership(client: Client, user_id: uuid.UUID) -> dict | None:
    result = (
        client.table("merchant_users")
        .select("merchant_id, role")
        .eq("user_id", str(user_id))
        .eq("status", "active")
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else None


def _find_submission(client: Client, merchant_id: uuid.UUID) -> dict | None:
    result = (
        client.table("onboarding_submissions").select("*").eq("merchant_id", str(merchant_id)).execute()
    )
    rows = result.data or []
    return rows[0] if rows else None


def _submission_data(payload: OnboardingMerchantAccountCreate) -> dict[str, Any]:
    return {
        "nature_of_business": payload.nature_of_business,
        "business_category": payload.business_category,
        "physical_address": payload.physical_address,
        "region_city": payload.region_city,
        "website_url": payload.website_url,
        "services_needed": [s.value for s in payload.services_needed],
        "accepted_terms": True,
        "accepted_privacy": True,
        "accepted_at": utc_now_iso(),
        "review_status": AccountStatus.PENDING_VERIFICATION.value,
        "review_note": None,
        "reviewed_by": None,
        "reviewed_at": None,
    }


def create_merchant_onboarding(
    client: Client, *, user: AuthenticatedUser, payload: OnboardingMerchantAccountCreate
) -> dict:
    if not payload.accepted_terms:
        raise ValidationAPIError("You must accept the Infinity Africa Terms of Service")
    if not payload.accepted_privacy:
        raise ValidationAPIError("You must accept the Infinity Africa Privacy Policy")

    membership = _find_active_membership(client, user.id)

    if membership:
        merchant_id = uuid.UUID(membership["merchant_id"])
        submission = _find_submission(client, merchant_id)

        if not submission or submission["review_status"] not in _RESUBMITTABLE_STATUSES:
            raise ConflictError("You already have a merchant account")

        # Resubmission after rejection/info-requested: update the existing
        # merchant profile + submission in place rather than creating a
        # second merchant — this is what "unless business rules allow"
        # covers, not a duplicate.
        merchant = update_row(
            client,
            "merchants",
            merchant_id,
            {"business_name": payload.business_name, "contact_phone": payload.contact_phone},
        )
        update_row(
            client,
            "onboarding_submissions",
            uuid.UUID(submission["id"]),
            {**_submission_data(payload), "submitted_at": utc_now_iso()},
        )

        write_audit_log(
            client,
            actor_id=user.id,
            actor_type="user",
            merchant_id=merchant_id,
            action="merchant.onboarding_resubmitted",
            resource_type="merchant",
            resource_id=merchant_id,
        )
        return merchant

    merchant = insert_row(
        client,
        "merchants",
        {
            "business_name": payload.business_name,
            "country": "TZ",
            "currency": "TZS",
            "contact_email": user.email,
            "contact_phone": payload.contact_phone,
            "status": "pending",
            "kyc_status": "unverified",
            "merchant_code": generate_merchant_code(client),
        },
    )
    merchant_id = uuid.UUID(merchant["id"])

    insert_row(
        client,
        "merchant_users",
        {
            "merchant_id": str(merchant_id),
            "user_id": str(user.id),
            "role": "MERCHANT_ADMIN",
            "status": "active",
        },
    )

    insert_row(
        client,
        "onboarding_submissions",
        {"merchant_id": str(merchant_id), "submitted_at": utc_now_iso(), **_submission_data(payload)},
    )

    write_audit_log(
        client,
        actor_id=user.id,
        actor_type="user",
        merchant_id=merchant_id,
        action="merchant.onboarding_submitted",
        resource_type="merchant",
        resource_id=merchant_id,
    )

    # Internal notification only — never confuse with send_merchant_welcome_email
    # (that one fires on *approval*, to the merchant; this one fires on
    # *submission*, to the CEO). Best-effort, same defense-in-depth
    # try/except as every other courtesy email in this codebase.
    try:
        send_new_merchant_signup_notification_email(client, merchant=merchant)
    except Exception:  # noqa: BLE001, S110
        pass

    return merchant


def get_onboarding_status(client: Client, *, user: AuthenticatedUser) -> dict:
    membership = _find_active_membership(client, user.id)
    if not membership:
        return {
            "has_account": False,
            "onboarding_completed": False,
            "merchant_id": None,
            "account_status": None,
            "next_path": "/onboarding",
        }

    merchant_id = uuid.UUID(membership["merchant_id"])
    submission = _find_submission(client, merchant_id)

    if not submission:
        return {
            "has_account": True,
            "onboarding_completed": False,
            "merchant_id": merchant_id,
            "account_status": None,
            "next_path": "/onboarding",
        }

    review_status = submission["review_status"]
    completed = review_status in _ONBOARDED_STATUSES

    return {
        "has_account": True,
        "onboarding_completed": completed,
        "merchant_id": merchant_id,
        "account_status": review_status,
        "next_path": "/merchant/overview" if completed else "/onboarding",
    }


def _extension_for(file: UploadFile) -> str:
    if file.filename and "." in file.filename:
        return "." + file.filename.rsplit(".", 1)[-1].lower()
    guessed = mimetypes.guess_extension(file.content_type or "") or ""
    return guessed


async def register_onboarding_document(
    client: Client,
    *,
    merchant_id: uuid.UUID,
    document_type: DocumentType,
    file: UploadFile,
    uploaded_by: uuid.UUID,
) -> dict:
    if file.content_type not in _ALLOWED_DOCUMENT_MIME_TYPES:
        raise ValidationAPIError(f"{document_type.value} must be a PDF, JPG, or PNG file")

    content = await file.read()
    if not content:
        raise ValidationAPIError(f"{document_type.value} file is empty")

    path = f"{merchant_id}/{document_type.value}{_extension_for(file)}"
    client.storage.from_(_BUCKET).upload(
        path, content, {"content-type": file.content_type or "application/octet-stream", "upsert": "true"}
    )

    data = {
        "merchant_id": str(merchant_id),
        "document_type": document_type.value,
        "file_path": path,
        "original_filename": file.filename or document_type.value,
        "mime_type": file.content_type or "application/octet-stream",
        "size_bytes": len(content),
        "upload_status": "UPLOADED",
        "uploaded_by": str(uploaded_by),
        "uploaded_at": utc_now_iso(),
    }

    existing = (
        client.table("onboarding_documents")
        .select("id")
        .eq("merchant_id", str(merchant_id))
        .eq("document_type", document_type.value)
        .execute()
    )
    rows = existing.data or []
    if rows:
        return update_row(client, "onboarding_documents", uuid.UUID(rows[0]["id"]), data) or data
    return insert_row(client, "onboarding_documents", data)


def get_document_signed_url(client: Client, document: dict, *, expires_in: int = 300) -> str | None:
    try:
        result = client.storage.from_(_BUCKET).create_signed_url(document["file_path"], expires_in)
    except StorageException:
        return None
    return result.get("signedURL") or result.get("signedUrl")


# --- Super-admin review -----------------------------------------------------


def _rollup_document_status(documents: list[dict]) -> str:
    statuses = [d["upload_status"] for d in documents]
    if any(s == "REJECTED" for s in statuses):
        return "REJECTED"
    if len(documents) < len(DocumentType) or any(s == "UPLOADED" for s in statuses):
        return "UPLOADED"
    return "VERIFIED"


def _to_submission_row(submission: dict, merchant: dict, documents: list[dict]) -> dict:
    return {
        "id": submission["id"],
        "merchant_id": submission["merchant_id"],
        "merchant_code": merchant.get("merchant_code"),
        "business_name": merchant.get("business_name", ""),
        # `or ""`, not `.get(..., "")` — the merchant row can have the key
        # present but set to None (contact_email is DB-required today, but
        # this response must never 500 if that's ever not true — see
        # app/services/email.py::send_merchant_welcome_email's own handling
        # of a missing merchant email).
        "owner_email": merchant.get("contact_email") or "",
        "contact_phone": merchant.get("contact_phone"),
        "nature_of_business": submission["nature_of_business"],
        "business_category": submission["business_category"],
        "physical_address": submission["physical_address"],
        "region_city": submission["region_city"],
        "website_url": submission.get("website_url"),
        "services_needed": submission.get("services_needed") or [],
        "review_status": submission["review_status"],
        "review_note": submission.get("review_note"),
        "document_status": _rollup_document_status(documents),
        "submitted_at": submission["submitted_at"],
        "updated_at": submission["updated_at"],
        "documents": documents,
    }


def list_onboarding_submissions(client: Client) -> list[dict]:
    submissions = (
        client.table("onboarding_submissions").select("*").order("submitted_at", desc=True).execute()
    ).data or []
    if not submissions:
        return []

    documents = client.table("onboarding_documents").select("*").execute().data or []
    docs_by_merchant: dict[str, list[dict]] = {}
    for doc in documents:
        docs_by_merchant.setdefault(doc["merchant_id"], []).append(doc)

    rows = []
    for submission in submissions:
        merchant = get_by_id(client, "merchants", uuid.UUID(submission["merchant_id"])) or {}
        rows.append(_to_submission_row(submission, merchant, docs_by_merchant.get(submission["merchant_id"], [])))
    return rows


def get_onboarding_submission(client: Client, submission_id: uuid.UUID) -> dict:
    submission = get_by_id(client, "onboarding_submissions", submission_id)
    if not submission:
        raise NotFoundError("Onboarding submission not found")

    merchant = get_by_id(client, "merchants", uuid.UUID(submission["merchant_id"])) or {}
    documents = (
        client.table("onboarding_documents")
        .select("*")
        .eq("merchant_id", submission["merchant_id"])
        .execute()
    ).data or []
    for doc in documents:
        doc["signed_url"] = get_document_signed_url(client, doc)

    return _to_submission_row(submission, merchant, documents)


def _missing_required_documents(client: Client, merchant_id: uuid.UUID) -> list[str]:
    documents = (
        client.table("onboarding_documents")
        .select("document_type, upload_status")
        .eq("merchant_id", str(merchant_id))
        .execute()
    ).data or []
    present = {d["document_type"] for d in documents if d["upload_status"] != "REJECTED"}
    return [doc_type.value for doc_type in _REQUIRED_APPROVAL_DOCUMENTS if doc_type.value not in present]


def approve_onboarding_submission(
    client: Client,
    *,
    submission_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    pricing: PricingRuleCreate | None = None,
) -> dict:
    submission = get_by_id(client, "onboarding_submissions", submission_id)
    if not submission:
        raise NotFoundError("Onboarding submission not found")

    merchant_id = uuid.UUID(submission["merchant_id"])
    merchant = get_by_id(client, "merchants", merchant_id)
    if not merchant:
        raise NotFoundError("Merchant not found")

    missing = _missing_required_documents(client, merchant_id)
    if missing:
        raise ValidationAPIError(
            f"Cannot approve: missing required document(s): {', '.join(missing)}"
        )

    updated = update_row(
        client,
        "onboarding_submissions",
        submission_id,
        {
            "review_status": AccountStatus.VERIFIED.value,
            "review_note": None,
            "reviewed_by": str(reviewer_id),
            "reviewed_at": utc_now_iso(),
        },
    )
    update_row(client, "merchants", merchant_id, {"status": "active", "kyc_status": "verified"})

    # Lazily creates the merchant's wallet ledger account if it doesn't
    # already exist — same get-or-create path every collection/withdrawal
    # uses, just triggered explicitly here so a freshly-approved merchant
    # always has one rather than waiting for their first transaction.
    get_wallet_balance(client, merchant_id=merchant_id, currency=merchant.get("currency", "TZS"))

    # Merchant-specific pricing is optional — when the Super Admin doesn't
    # provide any, no row is created here and merchant_pricing_rules'
    # existing precedence resolver (app/services/withdrawals/fee_calculator.py)
    # falls back to whatever platform-wide rule (merchant_id IS NULL) is
    # configured, exactly as it already does for every other merchant.
    if pricing is not None:
        fields = pricing.model_dump(mode="json")
        if fields.get("effective_from") is None:
            fields["effective_from"] = utc_now_iso()
        insert_row(
            client,
            "merchant_pricing_rules",
            {"merchant_id": str(merchant_id), "created_by": str(reviewer_id), **fields},
        )

    write_audit_log(
        client,
        actor_id=reviewer_id,
        actor_type="user",
        merchant_id=merchant_id,
        action="onboarding.approved",
        resource_type="onboarding_submission",
        resource_id=submission_id,
        metadata={"custom_pricing_assigned": pricing is not None},
    )

    # Welcome email is a courtesy, not part of approval itself — never let
    # it fail the approval (send_merchant_welcome_email already never
    # raises on its own; this is a second layer of defense in depth).
    # Always calls send_merchant_welcome_email regardless of whether
    # contact_email looks present — it already handles a missing
    # recipient itself (logs + no-ops, never falls back to CEO_EMAIL).
    # Checked independently here too, not by inspecting that function's
    # return value, so the Super Admin warning below is specifically about
    # a missing address, not conflated with a Resend delivery failure.
    welcome_email_warning = None
    try:
        settings = get_settings()
        if not merchant.get("contact_email"):
            welcome_email_warning = "Merchant approved, but welcome email was not sent because merchant email is missing."
        send_merchant_welcome_email(
            client, merchant=merchant, portal_url=f"{settings.public_app_url}/merchant/login"
        )
    except Exception:  # noqa: BLE001, S110
        pass

    result = get_onboarding_submission(client, submission_id) if updated else submission
    if welcome_email_warning:
        result = {**result, "welcome_email_warning": welcome_email_warning}
    return result


def _set_review_status(
    client: Client, *, submission_id: uuid.UUID, reviewer_id: uuid.UUID, status: AccountStatus, note: str | None, action: str
) -> dict:
    submission = get_by_id(client, "onboarding_submissions", submission_id)
    if not submission:
        raise NotFoundError("Onboarding submission not found")

    update_row(
        client,
        "onboarding_submissions",
        submission_id,
        {
            "review_status": status.value,
            "review_note": note,
            "reviewed_by": str(reviewer_id),
            "reviewed_at": utc_now_iso(),
        },
    )

    write_audit_log(
        client,
        actor_id=reviewer_id,
        actor_type="user",
        merchant_id=uuid.UUID(submission["merchant_id"]),
        action=action,
        resource_type="onboarding_submission",
        resource_id=submission_id,
        metadata={"note": note} if note else None,
    )
    return get_onboarding_submission(client, submission_id)


def reject_onboarding_submission(
    client: Client, *, submission_id: uuid.UUID, reviewer_id: uuid.UUID, note: str | None
) -> dict:
    return _set_review_status(
        client,
        submission_id=submission_id,
        reviewer_id=reviewer_id,
        status=AccountStatus.REJECTED,
        note=note,
        action="onboarding.rejected",
    )


def request_more_info_onboarding_submission(
    client: Client, *, submission_id: uuid.UUID, reviewer_id: uuid.UUID, note: str | None
) -> dict:
    return _set_review_status(
        client,
        submission_id=submission_id,
        reviewer_id=reviewer_id,
        status=AccountStatus.INFO_REQUESTED,
        note=note,
        action="onboarding.info_requested",
    )
