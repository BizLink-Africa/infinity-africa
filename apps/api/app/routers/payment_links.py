"""Payment Links: shareable checkout links a merchant creates for a
specific amount, which a customer pays without any account of their own.

Flat resource routes — there's no merchant_id path segment. The caller's
merchant is resolved from their API key, or checked against merchant_id in
the request body/fetched row for a dashboard JWT caller — see
app.auth.get_authenticated_caller / authorize_merchant_action.
"""

import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Header, status

from app.auth import (
    authorize_merchant_action,
    get_authenticated_caller,
    require_api_key_scope,
)
from app.core.errors import ConflictError, NotFoundError, ValidationAPIError
from app.database.session import get_supabase_admin
from app.schemas.auth import AuthenticatedCaller
from app.schemas.common import APIResponse
from app.schemas.enums import CollectionMethod, UserRole
from app.schemas.payment_links import (
    PaymentLinkCollectRequest,
    PaymentLinkCreate,
    PaymentLinkResponse,
    PaymentLinkWalletPushRequest,
    PaymentLinkWalletPushResponse,
    PublicCollectionStatusResponse,
    PublicPaymentLinkResponse,
)
from app.services.audit import write_audit_log
from app.services.collections import execute_collection, execute_dynamic_qr_collection
from app.services.crud import execute_maybe_single, get_by_id, insert_row, update_row
from app.services.idempotency import run_idempotent
from app.services.payment_links import (
    batch_collection_counts,
    build_public_url,
    generate_public_slug,
    with_effective_status,
)
from app.services.wallet_push import execute_wallet_push_for_payment_link

router = APIRouter(prefix="/payment-links", tags=["payment-links"])
public_router = APIRouter(prefix="/public/payment-links", tags=["payment-links (public)"])

_DASHBOARD_ROLES = (UserRole.MERCHANT_ADMIN, UserRole.MERCHANT_STAFF)


def _to_response(row: dict, *, attempt_count: int = 0) -> PaymentLinkResponse:
    return PaymentLinkResponse(
        **row, public_url=build_public_url(row["public_slug"]), attempt_count=attempt_count
    )


@router.post("", response_model=APIResponse[PaymentLinkResponse], status_code=status.HTTP_201_CREATED)
async def create_payment_link(
    payload: PaymentLinkCreate,
    caller: Annotated[AuthenticatedCaller, Depends(get_authenticated_caller)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
):
    """Callable from the dashboard (JWT) or a merchant's own backend (API key)."""
    authorize_merchant_action(caller, payload.merchant_id, *_DASHBOARD_ROLES)
    require_api_key_scope(caller, "payment_links:write")
    client = get_supabase_admin()

    async def _handler() -> tuple[int, dict]:
        data = payload.model_dump(mode="json", exclude={"allowed_payment_methods"})
        data["allowed_payment_methods"] = [m.value for m in payload.allowed_payment_methods]
        data["public_slug"] = generate_public_slug()
        data["status"] = "ACTIVE"

        row = insert_row(client, "payment_links", data)

        write_audit_log(
            client,
            actor_id=caller.actor_id,
            actor_type=caller.actor_type,
            merchant_id=payload.merchant_id,
            action="payment_link.created",
            resource_type="payment_link",
            resource_id=uuid.UUID(row["id"]),
        )

        return status.HTTP_201_CREATED, row

    _status_code, body = await run_idempotent(
        client,
        merchant_id=payload.merchant_id,
        endpoint="POST /v1/payment-links",
        idempotency_key=idempotency_key,
        request_payload=payload.model_dump(mode="json"),
        handler=_handler,
    )

    return APIResponse(data=_to_response(body), meta=None)


@router.get("/{link_id}", response_model=APIResponse[PaymentLinkResponse])
def get_payment_link(
    link_id: uuid.UUID,
    caller: Annotated[AuthenticatedCaller, Depends(get_authenticated_caller)],
):
    client = get_supabase_admin()
    row = get_by_id(client, "payment_links", link_id)
    if not row:
        raise NotFoundError("Payment link not found")

    authorize_merchant_action(caller, uuid.UUID(row["merchant_id"]), *_DASHBOARD_ROLES)
    require_api_key_scope(caller, "payment_links:read")
    row = with_effective_status(client, row)
    counts = batch_collection_counts(client, {row["id"]})

    return APIResponse(data=_to_response(row, attempt_count=counts.get(row["id"], 0)))


@router.patch("/{link_id}/cancel", response_model=APIResponse[PaymentLinkResponse])
def cancel_payment_link(
    link_id: uuid.UUID,
    caller: Annotated[AuthenticatedCaller, Depends(get_authenticated_caller)],
):
    client = get_supabase_admin()
    row = get_by_id(client, "payment_links", link_id)
    if not row:
        raise NotFoundError("Payment link not found")

    merchant_id = uuid.UUID(row["merchant_id"])
    authorize_merchant_action(caller, merchant_id, *_DASHBOARD_ROLES)
    require_api_key_scope(caller, "payment_links:write")

    row = with_effective_status(client, row)

    if row["status"] == "PAID":
        raise ConflictError("A paid payment link cannot be cancelled")

    if row["status"] != "CANCELLED":
        row = update_row(client, "payment_links", link_id, {"status": "CANCELLED"}) or row

        write_audit_log(
            client,
            actor_id=caller.actor_id,
            actor_type=caller.actor_type,
            merchant_id=merchant_id,
            action="payment_link.cancelled",
            resource_type="payment_link",
            resource_id=link_id,
        )

    return APIResponse(data=_to_response(row))


# --- Public (unauthenticated) — "public customers can access only valid
# payment links" is enforced right here, not left to the caller. ----------


@public_router.get("/{public_slug}", response_model=APIResponse[PublicPaymentLinkResponse])
def get_public_payment_link(public_slug: str):
    client = get_supabase_admin()
    link = execute_maybe_single(
        client.table("payment_links").select("*").eq("public_slug", public_slug).maybe_single()
    )

    if not link:
        raise NotFoundError("Payment link not found")

    link = with_effective_status(client, link)
    merchant = get_by_id(client, "merchants", uuid.UUID(link["merchant_id"]))
    merchant_name = merchant["business_name"] if merchant else "Unknown merchant"

    return APIResponse(data=PublicPaymentLinkResponse(**link, merchant_name=merchant_name))


_PAYMENT_STATUS_COPY: dict[str, tuple[str, str]] = {
    "PENDING": ("pending", "Payment request sent to your phone. Please approve using your PIN."),
    "INPROGRESS": ("pending", "Payment request sent to your phone. Please approve using your PIN."),
    "CANCELLED": ("cancelled", "This payment was cancelled."),
    "USERCANCELLED": ("user_cancelled", "You cancelled this payment."),
    "REJECTED": ("rejected", "This payment was rejected."),
}


@public_router.get(
    "/{public_slug}/collections/{collection_id}/status", response_model=APIResponse[PublicCollectionStatusResponse]
)
def get_public_collection_status(public_slug: str, collection_id: uuid.UUID):
    """Polled by the customer payment page after a Mobile Money Push
    submission (POST .../pay/wallet-push) — the payment link's own
    status only ever reflects PAID once, so a customer waiting to see
    "cancelled"/"rejected" specifically needs the collection's own
    status, not the link's. Scoped to collections that actually belong
    to this public_slug's payment link, so a collection_id can't be used
    to probe an unrelated one."""
    client = get_supabase_admin()
    link = execute_maybe_single(
        client.table("payment_links").select("id").eq("public_slug", public_slug).maybe_single()
    )
    if not link:
        raise NotFoundError("Payment link not found")

    collection = execute_maybe_single(
        client.table("collections")
        .select("status,provider_payment_status,failure_reason")
        .eq("id", str(collection_id))
        .eq("payment_link_id", link["id"])
        .maybe_single()
    )
    if not collection:
        raise NotFoundError("Collection not found")

    if collection["status"] == "successful":
        status, message = "completed", "Payment completed successfully."
    elif collection["status"] == "processing":
        status, message = _PAYMENT_STATUS_COPY.get(
            collection.get("provider_payment_status") or "PENDING",
            ("pending", "Payment request sent to your phone. Please approve using your PIN."),
        )
    else:
        status, message = _PAYMENT_STATUS_COPY.get(
            collection.get("provider_payment_status") or "",
            ("failed", collection.get("failure_reason") or "This payment could not be completed."),
        )

    return APIResponse(data=PublicCollectionStatusResponse(status=status, message=message))


@public_router.post(
    "/{public_slug}/collect", response_model=APIResponse[dict], status_code=status.HTTP_202_ACCEPTED
)
async def collect_payment_link(
    public_slug: str,
    payload: PaymentLinkCollectRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
):
    client = get_supabase_admin()
    link = execute_maybe_single(
        client.table("payment_links").select("*").eq("public_slug", public_slug).maybe_single()
    )

    if not link:
        raise NotFoundError("Payment link not found")

    merchant_id = uuid.UUID(link["merchant_id"])

    async def _handler() -> tuple[int, dict]:
        # Checked here, not before run_idempotent, so a retry of an
        # already-succeeded request replays the stored response instead of
        # failing because the link is now PAID as a *result* of that first
        # request.
        current = with_effective_status(client, link)
        if current["status"] != "ACTIVE":
            raise ConflictError(f"This payment link cannot be paid (status: {current['status']})")
        if payload.method.value not in current["allowed_payment_methods"]:
            raise ValidationAPIError("This payment method isn't accepted on this payment link")

        if payload.method == CollectionMethod.DYNAMIC_QR:
            # No phone push to synchronously check the status of — the QR
            # has to exist before anyone can scan it. Stays PROCESSING until
            # the /v1/webhooks/selcom callback resolves it.
            collection, qr_result = await execute_dynamic_qr_collection(
                client,
                merchant_id=merchant_id,
                amount=Decimal(str(current["amount"])),
                currency=current["currency"],
                customer_id=uuid.UUID(current["customer_id"]) if current.get("customer_id") else None,
                customer_phone=payload.customer_phone or current.get("customer_phone"),
                payment_link_id=uuid.UUID(current["id"]),
            )
            body = {
                **collection,
                "qr_payload": qr_result.qr_payload,
                "qr_expires_at": qr_result.qr_expires_at.isoformat(),
                "expires_at": qr_result.qr_expires_at.isoformat(),
            }
            return status.HTTP_202_ACCEPTED, body

        collection = await execute_collection(
            client,
            merchant_id=merchant_id,
            method=payload.method,
            amount=Decimal(str(current["amount"])),
            currency=current["currency"],
            customer_id=uuid.UUID(current["customer_id"]) if current.get("customer_id") else None,
            customer_phone=payload.customer_phone or current.get("customer_phone"),
            payment_link_id=uuid.UUID(current["id"]),
        )
        return status.HTTP_202_ACCEPTED, collection

    _status_code, body = await run_idempotent(
        client,
        merchant_id=merchant_id,
        endpoint="POST /public/payment-links/{slug}/collect",
        idempotency_key=idempotency_key,
        request_payload={"public_slug": public_slug, **payload.model_dump(mode="json")},
        handler=_handler,
    )

    return APIResponse(data=body)


@public_router.post(
    "/{public_slug}/pay/wallet-push",
    response_model=APIResponse[PaymentLinkWalletPushResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def pay_payment_link_wallet_push(
    public_slug: str,
    payload: PaymentLinkWalletPushRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
):
    """Selcom Checkout's two-step create-order-minimal -> wallet-payment
    flow (Push STK/USSD/mobile money push), distinct from
    collect_payment_link() above, which still goes through the older,
    unconfirmed app/services/selcom/ placeholder. Never credits the
    merchant, posts a ledger entry, or marks this link PAID — see
    app/services/wallet_push.py's module docstring for why, and what's
    still missing before that can happen."""
    client = get_supabase_admin()
    link = execute_maybe_single(
        client.table("payment_links").select("*").eq("public_slug", public_slug).maybe_single()
    )

    if not link:
        raise NotFoundError("Payment link not found")

    merchant_id = uuid.UUID(link["merchant_id"])

    async def _handler() -> tuple[int, dict]:
        # Checked here, not before run_idempotent, so a retry of an
        # already-in-flight request replays the stored response rather
        # than failing — same convention as collect_payment_link above.
        current = with_effective_status(client, link)
        if current["status"] != "ACTIVE":
            raise ConflictError(f"This payment link cannot be paid (status: {current['status']})")

        collection = await execute_wallet_push_for_payment_link(
            client, payment_link=current, buyer_phone=payload.customer_phone
        )

        payment_status = "failed" if collection["status"] == "failed" else "pending"
        message = (
            collection.get("failure_reason") or collection.get("provider_message") or "This payment attempt failed."
            if payment_status == "failed"
            else "Payment request sent to your phone. Please approve using your PIN."
        )
        body = {
            "collection_id": collection["id"],
            "payment_status": payment_status,
            "message": message,
        }
        return status.HTTP_202_ACCEPTED, body

    _status_code, body = await run_idempotent(
        client,
        merchant_id=merchant_id,
        endpoint="POST /public/payment-links/{slug}/pay/wallet-push",
        idempotency_key=idempotency_key,
        request_payload={"public_slug": public_slug, **payload.model_dump(mode="json")},
        handler=_handler,
    )

    return APIResponse(data=PaymentLinkWalletPushResponse(**body))
