import json
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError

from app.auth import require_role
from app.config import get_settings
from app.core.errors import NotFoundError, ValidationAPIError
from app.core.pagination import PaginationParams, build_page_meta, pagination_params
from app.core.time import utc_now_iso
from app.database.session import get_supabase_admin
from app.schemas.auth import AuthenticatedUser
from app.schemas.common import APIResponse
from app.schemas.enums import UserRole
from app.schemas.selcom_checkout_webhooks import SelcomCheckoutWebhookPayload
from app.schemas.webhooks import SelcomWebhookPayload, WebhookEventResponse
from app.services.checkout_reconciliation import (
    complete_checkout_collection_once,
    find_collection_by_order_id,
    find_collection_by_transid,
)
from app.services.collections import resolve_collection_from_callback
from app.services.crud import get_for_merchant, list_for_merchant, update_row
from app.services.disbursements import (
    resolve_disbursement_from_callback,
    reverse_successful_disbursement_from_callback,
)
from app.services.selcom.webhooks import verify_selcom_signature
from app.services.selcom_checkout.signer import verify_webhook_signature
from app.services.webhooks import store_incoming_selcom_event

router = APIRouter(prefix="/merchants/{merchant_id}/webhooks", tags=["webhooks"])
callback_router = APIRouter(prefix="/webhooks", tags=["webhooks (provider callback)"])

logger = logging.getLogger("infinity.webhooks")

_HEADER_NAMES_NEVER_STORED = {"authorization", "cookie"}


def _safe_headers_for_storage(headers) -> dict[str, str]:
    """Every header name Selcom's callback actually sent, for diagnosing
    an unexpected/rejected signature scheme — see
    selcom_checkout_webhook's docstring. Defensive only: a provider
    webhook has no legitimate reason to carry Authorization/Cookie, but
    they're excluded on principle rather than assumed absent."""
    return {key: value for key, value in headers.items() if key.lower() not in _HEADER_NAMES_NEVER_STORED}

_DASHBOARD_ROLES = (UserRole.MERCHANT_ADMIN, UserRole.MERCHANT_STAFF)


@router.get("", response_model=APIResponse[list[WebhookEventResponse]])
def list_webhook_events(
    merchant_id: uuid.UUID,
    _actor: Annotated[AuthenticatedUser, Depends(require_role(*_DASHBOARD_ROLES))],
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
):
    """The "Webhook Logs" merchants/admins see — delivery status per event.
    This only records events; a background worker (not built yet) is what
    would actually deliver them and update these rows."""
    client = get_supabase_admin()
    rows, total = list_for_merchant(client, "webhook_events", merchant_id=merchant_id, pagination=pagination)
    data = [WebhookEventResponse(**row) for row in rows]
    return APIResponse(data=data, meta=build_page_meta(pagination, total))


@router.get("/{webhook_event_id}", response_model=APIResponse[WebhookEventResponse])
def get_webhook_event(
    merchant_id: uuid.UUID,
    webhook_event_id: uuid.UUID,
    _actor: Annotated[AuthenticatedUser, Depends(require_role(*_DASHBOARD_ROLES))],
):
    client = get_supabase_admin()
    row = get_for_merchant(client, "webhook_events", merchant_id=merchant_id, row_id=webhook_event_id)
    if not row:
        raise NotFoundError("Webhook event not found")
    return APIResponse(data=WebhookEventResponse(**row))


@callback_router.get("/selcom", response_model=APIResponse[dict])
async def selcom_webhook_reachability_check():
    """Answers a provider's own "is this URL reachable" probe (e.g. Selcom's
    Business portal "Test URL" button when configuring a callback), which
    hits this path with a plain unauthenticated GET expecting a 2xx — not a
    real callback delivery. Real deliveries are POSTs, handled below, and
    still require a valid signature; this GET path carries no data and
    performs no action, so it doesn't weaken that verification.
    """
    return APIResponse(data={"status": "ok"})


@callback_router.post("/selcom", response_model=APIResponse[dict])
async def selcom_webhook(request: Request):
    """Where a real Selcom callback would land, resolving a collection or
    disbursement that was left `processing`. In SELCOM_MODE=mock (the
    default — see MockSelcomClient) nothing ever calls this, since the mock
    resolves synchronously — this is the receiving side, ready for
    SELCOM_MODE=live (see docs/selcom-live-go-live.md).

    Deliberately unauthenticated like any provider webhook — instead it's
    verified via an HMAC signature (X-Selcom-Signature, over the raw body,
    see app/services/selcom/webhooks.py) and every delivery is
    logged to selcom_webhook_events, whose unique (provider, event_id)
    guards against reprocessing a retried/duplicate delivery.
    """
    raw_body = await request.body()
    raw_text = raw_body.decode("utf-8", errors="replace")
    signature = request.headers.get("X-Selcom-Signature")
    settings = get_settings()
    signature_valid = verify_selcom_signature(
        raw_body=raw_body, signature=signature, secret=settings.selcom_webhook_secret
    )

    try:
        body = json.loads(raw_body) if raw_body else {}
    except ValueError:
        body = {}

    event_id = str(body.get("event_id") or body.get("provider_reference") or uuid.uuid4())
    event_type = str(body.get("event_type") or "unknown")

    client = get_supabase_admin()
    stored, is_duplicate = store_incoming_selcom_event(
        client,
        event_id=event_id,
        event_type=event_type,
        raw_body=raw_text,
        signature=signature,
        signature_valid=signature_valid,
    )
    if is_duplicate:
        return APIResponse(data={"status": "duplicate", "event_id": event_id})

    if not signature_valid:
        update_row(
            client,
            "selcom_webhook_events",
            uuid.UUID(stored["id"]),
            {"status": "failed", "processing_error": "invalid signature"},
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")

    try:
        payload = SelcomWebhookPayload.model_validate(body)
    except ValidationError as exc:
        errors = jsonable_encoder(exc.errors())
        update_row(
            client,
            "selcom_webhook_events",
            uuid.UUID(stored["id"]),
            {"status": "failed", "processing_error": json.dumps(errors)},
        )
        raise ValidationAPIError("Invalid webhook payload", details=errors) from exc

    result = _dispatch_selcom_event(client, payload)

    update_row(
        client,
        "selcom_webhook_events",
        uuid.UUID(stored["id"]),
        {"status": "processed", "processed_at": utc_now_iso()},
    )

    return APIResponse(data=result)


def _dispatch_selcom_event(client, payload: SelcomWebhookPayload) -> dict:
    if payload.event_type.startswith("collection."):
        resolved_status = "successful" if payload.event_type.endswith(".success") else "failed"
        collection = resolve_collection_from_callback(
            client,
            provider_reference=payload.provider_reference,
            status=resolved_status,
            failure_reason=payload.failure_reason,
        )
        if collection:
            return {"resolved": "collection", "id": collection["id"]}
        return {"resolved": "none", "message": "No pending collection matched this provider_reference"}

    if payload.event_type.endswith(".reversed"):
        # An already-SUCCESS payout bounced after settlement (e.g. an
        # invalid bank account discovered late) — a different resolution
        # path than PROCESSING -> success/failed below, so it's checked
        # first: a ".success"/".failed" style status computation wouldn't
        # make sense for it.
        disbursement = reverse_successful_disbursement_from_callback(
            client, provider_reference=payload.provider_reference, reason=payload.failure_reason
        )
        if disbursement:
            return {"resolved": "disbursement_reversal", "id": disbursement["id"]}
        return {"resolved": "none", "message": "No successful disbursement matched this provider_reference"}

    resolved_status = "successful" if payload.event_type.endswith(".success") else "failed"
    disbursement = resolve_disbursement_from_callback(
        client,
        provider_reference=payload.provider_reference,
        status=resolved_status,
        failure_reason=payload.failure_reason,
    )
    if disbursement:
        return {"resolved": "disbursement", "id": disbursement["id"]}
    return {"resolved": "none", "message": "No pending disbursement matched this provider_reference"}


@callback_router.get("/selcom/checkout", response_model=APIResponse[dict])
async def selcom_checkout_webhook_reachability_check():
    """Same reachability-probe answer as selcom_webhook_reachability_check
    above, for Selcom's Checkout product's own callback-configuration
    "Test URL" check — see that function's docstring."""
    return APIResponse(data={"status": "ok"})


@callback_router.post("/selcom/checkout", response_model=APIResponse[dict])
async def selcom_checkout_webhook(request: Request):
    """Selcom Checkout's webhook callback — the async resolution path for
    a wallet-push collection left "processing" after
    process_wallet_payment()'s usual PENDING/111 response
    (app/services/wallet_push.py). Distinct product/signing scheme from
    selcom_webhook above (RSA/HMAC-style Digest headers confirmed for
    outbound Checkout requests, mirrored here for verifying inbound ones
    — see app/services/selcom_checkout/signer.py::verify_webhook_signature
    for the exact scheme and, importantly, why it's an inference not yet
    confirmed against a real delivery).

    Every delivery is logged to selcom_webhook_events (provider=
    "selcom_checkout", so it never collides with the older placeholder
    product's own events on event_id) before signature verification even
    runs, so the very first real delivery this backend ever receives can
    be inspected regardless of whether verification passes — that's how
    the "inferred" signing scheme above gets confirmed or corrected.

    Not the only way a collection resolves: POST /v1/merchant/collections/
    {id}/refresh-status and POST /v1/admin/collections/{id}/refresh-status
    query Selcom directly and apply the exact same completion logic
    (app/services/checkout_reconciliation.py), so a webhook that never
    arrives — or one this endpoint ends up rejecting because the
    signature inference above is wrong — doesn't strand a payment.
    """
    raw_body = await request.body()
    raw_text = raw_body.decode("utf-8", errors="replace")
    timestamp = request.headers.get("Timestamp")
    digest = request.headers.get("Digest")
    digest_method = request.headers.get("Digest-Method")
    signed_fields_header = request.headers.get("Signed-Fields")

    settings = get_settings()

    try:
        body = json.loads(raw_body) if raw_body else {}
    except ValueError:
        body = {}

    # Logged before signature verification runs, deliberately — this is
    # how we'll ever know a delivery arrived at all if the (unconfirmed)
    # signature scheme turns out wrong and rejects it. Timestamp/Digest/
    # Digest-Method/Signed-Fields are protocol metadata, not secrets —
    # safe to log (the actual secret is api_secret, never logged, never
    # included below). Also dumps every header *name* Selcom actually
    # sent — confirmed necessary on 2026-08-22: the first real delivery
    # arrived with all four of these expected headers completely absent,
    # meaning the inferred signing scheme guessed the wrong header names
    # (or Selcom simply doesn't sign this callback at all) — this is
    # what lets the next delivery answer that question instead of
    # guessing again.
    logger.info(
        "selcom_checkout webhook received: order_id=%s transid=%s reference=%s payment_status=%s "
        "Timestamp=%r Digest=%r Digest-Method=%r Signed-Fields=%r header_names=%s",
        body.get("order_id"),
        body.get("transid"),
        body.get("reference"),
        body.get("payment_status"),
        timestamp,
        digest,
        digest_method,
        signed_fields_header,
        sorted(request.headers.keys()),
    )

    signature_valid = verify_webhook_signature(
        body=body,
        timestamp=timestamp,
        digest=digest,
        digest_method=digest_method,
        signed_fields_header=signed_fields_header,
        api_secret=settings.selcom_checkout_api_secret,
    )

    event_id = str(body.get("transid") or uuid.uuid4())
    event_type = str(body.get("payment_status") or "unknown")

    client = get_supabase_admin()
    stored, is_duplicate = store_incoming_selcom_event(
        client,
        event_id=event_id,
        event_type=event_type,
        raw_body=raw_text,
        signature=digest,
        signature_valid=signature_valid,
        provider="selcom_checkout",
        raw_headers=_safe_headers_for_storage(request.headers),
    )
    if is_duplicate:
        return APIResponse(data={"status": "duplicate", "event_id": event_id})

    if not signature_valid:
        update_row(
            client,
            "selcom_webhook_events",
            uuid.UUID(stored["id"]),
            {"status": "failed", "processing_error": "invalid signature"},
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")

    try:
        payload = SelcomCheckoutWebhookPayload.model_validate(body)
    except ValidationError as exc:
        errors = jsonable_encoder(exc.errors())
        update_row(
            client,
            "selcom_webhook_events",
            uuid.UUID(stored["id"]),
            {"status": "failed", "processing_error": json.dumps(errors)},
        )
        raise ValidationAPIError("Invalid webhook payload", details=errors) from exc

    collection = find_collection_by_transid(client, transid=payload.transid) or find_collection_by_order_id(
        client, order_id=payload.order_id
    )
    if not collection:
        update_row(
            client,
            "selcom_webhook_events",
            uuid.UUID(stored["id"]),
            {"status": "failed", "processing_error": "no matching collection for this transid/order_id"},
        )
        raise NotFoundError("No matching collection found for this webhook")

    await complete_checkout_collection_once(
        client,
        collection_id=uuid.UUID(collection["id"]),
        payment_status=payload.payment_status,
        result=payload.result,
        resultcode=payload.resultcode,
        reference=payload.reference,
        transid=payload.transid,
        channel=payload.channel,
        raw_response=body,
    )

    update_row(
        client,
        "selcom_webhook_events",
        uuid.UUID(stored["id"]),
        {"status": "processed", "processed_at": utc_now_iso()},
    )

    return APIResponse(data={"status": "acknowledged"})
