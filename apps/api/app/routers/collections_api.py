"""The external developer Collections API — POST/GET /v1/collections...
See app/schemas/collections_api.py's module docstring for how this
relates to the older app/routers/collections.py endpoints, and
app/services/collections_api.py for the status/method vocabulary this
API commits to externally vs. this codebase's real internal one.

Every creation endpoint here is backed by the real, proven Selcom
Checkout integration (app/services/wallet_push.py,
app/services/selcom_checkout/client.py, etc.) — never the older,
unconfirmed app/services/selcom/ placeholder app/routers/collections.py
still uses for its own /ussd-push, /stk-push, /selcom-pesa-push,
/dynamic-qr endpoints.

Auth follows the exact same pattern as app/routers/collections.py and
app/routers/payment_links.py: get_authenticated_caller (API key or
dashboard JWT) + authorize_merchant_action (the request's own
merchant_id must match the caller) + require_api_key_scope. Every
creation endpoint requires an Idempotency-Key header, same convention
as every other money-moving endpoint in this codebase.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, status

from app.auth import (
    authorize_merchant_action,
    get_authenticated_caller,
    require_api_key_scope,
)
from app.core.errors import ConflictError, NotFoundError
from app.database.session import get_supabase_admin
from app.schemas.auth import AuthenticatedCaller
from app.schemas.collections_api import (
    CollectionCreateRequest,
    CollectionCreateResponse,
    CollectionPushCreateRequest,
    CollectionPushCreateResponse,
    CollectionQrCreateRequest,
    CollectionQrCreateResponse,
    CollectionStatusResponse,
)
from app.schemas.common import APIResponse
from app.schemas.enums import UserRole
from app.services.audit import write_audit_log
from app.services.checkout_reconciliation import refresh_checkout_collection_status
from app.services.collections_api import (
    find_collection_by_external_id,
    to_external_method,
    to_external_status,
)
from app.services.crud import insert_row
from app.services.dynamic_qr import execute_qr_collection
from app.services.idempotency import run_idempotent
from app.services.payment_links import build_public_url, generate_public_slug
from app.services.selcompesa_push import execute_selcompesa_push_collection
from app.services.wallet_push import execute_wallet_push_collection

router = APIRouter(prefix="/collections", tags=["collections-api"])

_DASHBOARD_ROLES = (UserRole.MERCHANT_ADMIN, UserRole.MERCHANT_STAFF)


def _status_response(row: dict) -> CollectionStatusResponse:
    return CollectionStatusResponse(
        collection_id=uuid.UUID(row["id"]),
        reference=row.get("merchant_reference"),
        status=to_external_status(row["status"]),
        amount=row["amount"],
        currency=row["currency"],
        method=to_external_method(row.get("method")),
        provider_payment_status=row.get("provider_payment_status"),
        failure_reason=row.get("failure_reason"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.post("", response_model=APIResponse[CollectionCreateResponse], status_code=status.HTTP_202_ACCEPTED)
async def create_collection(
    payload: CollectionCreateRequest,
    caller: Annotated[AuthenticatedCaller, Depends(get_authenticated_caller)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
):
    """The recommended flow for ecommerce/mobile apps: creates an
    Infinity Payment Page (internally the same payment_links resource
    Payment Links and Merchant Portal's "Request Collection" already
    use) and returns its URL. Redirect your customer to `payment_url` —
    they choose Mobile Money Push / Selcom Pesa / Scan QR themselves;
    you never pick a channel here."""
    authorize_merchant_action(caller, payload.merchant_id, *_DASHBOARD_ROLES)
    require_api_key_scope(caller, "collections:write")
    client = get_supabase_admin()

    async def _handler() -> tuple[int, dict]:
        row = insert_row(
            client,
            "payment_links",
            {
                "merchant_id": str(payload.merchant_id),
                "amount": str(payload.amount),
                "currency": payload.currency,
                "customer_name": payload.customer_name,
                "customer_phone": payload.customer_phone,
                "customer_email": payload.customer_email,
                "description": payload.description,
                "merchant_reference": payload.reference,
                "allowed_payment_methods": [],
                "success_redirect_url": payload.redirect_url,
                "failure_redirect_url": payload.cancel_url,
                "public_slug": generate_public_slug(),
                "status": "ACTIVE",
            },
        )
        write_audit_log(
            client,
            actor_id=caller.actor_id,
            actor_type=caller.actor_type,
            merchant_id=payload.merchant_id,
            action="collection.created",
            resource_type="payment_link",
            resource_id=uuid.UUID(row["id"]),
        )
        body = {
            "collection_id": row["id"],
            "reference": row.get("merchant_reference"),
            "status": "created",
            "payment_url": build_public_url(row["public_slug"]),
        }
        return status.HTTP_202_ACCEPTED, body

    _status_code, body = await run_idempotent(
        client,
        merchant_id=payload.merchant_id,
        endpoint="POST /v1/collections",
        idempotency_key=idempotency_key,
        request_payload=payload.model_dump(mode="json"),
        handler=_handler,
    )
    return APIResponse(data=CollectionCreateResponse(**body))


@router.post(
    "/wallet-push", response_model=APIResponse[CollectionPushCreateResponse], status_code=status.HTTP_202_ACCEPTED
)
async def create_wallet_push_collection(
    payload: CollectionPushCreateRequest,
    caller: Annotated[AuthenticatedCaller, Depends(get_authenticated_caller)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
):
    """Sends a real Mobile Money Push prompt immediately — best for a
    checkout where you already have the customer's phone number. A
    `202`/`"processing"` response means the prompt was sent, **not**
    that payment succeeded — never mark an order paid from this
    response; poll GET /v1/collections/{collection_id} or wait for the
    `collection.successful` webhook."""
    authorize_merchant_action(caller, payload.merchant_id, *_DASHBOARD_ROLES)
    require_api_key_scope(caller, "collections:write")
    client = get_supabase_admin()

    async def _handler() -> tuple[int, dict]:
        collection = await execute_wallet_push_collection(
            client,
            merchant_id=payload.merchant_id,
            amount=payload.amount,
            currency=payload.currency,
            customer_phone=payload.phone,
            customer_name=payload.customer_name,
            merchant_reference=payload.reference,
            description=payload.description,
        )
        message = (
            collection.get("failure_reason") or "This payment attempt failed."
            if collection["status"] == "failed"
            else "Payment prompt sent. Please approve on your phone."
        )
        body = {
            "collection_id": collection["id"],
            "reference": collection.get("merchant_reference"),
            "status": to_external_status(collection["status"]),
            "message": message,
        }
        return status.HTTP_202_ACCEPTED, body

    _status_code, body = await run_idempotent(
        client,
        merchant_id=payload.merchant_id,
        endpoint="POST /v1/collections/wallet-push",
        idempotency_key=idempotency_key,
        request_payload=payload.model_dump(mode="json"),
        handler=_handler,
    )
    return APIResponse(data=CollectionPushCreateResponse(**body))


@router.post(
    "/selcom-pesa", response_model=APIResponse[CollectionPushCreateResponse], status_code=status.HTTP_202_ACCEPTED
)
async def create_selcom_pesa_collection(
    payload: CollectionPushCreateRequest,
    caller: Annotated[AuthenticatedCaller, Depends(get_authenticated_caller)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
):
    """Sends a real Selcom Pesa prompt immediately. Same rule as
    wallet-push: `"processing"` means the prompt was sent, not that
    payment succeeded."""
    authorize_merchant_action(caller, payload.merchant_id, *_DASHBOARD_ROLES)
    require_api_key_scope(caller, "collections:write")
    client = get_supabase_admin()

    async def _handler() -> tuple[int, dict]:
        collection = await execute_selcompesa_push_collection(
            client,
            merchant_id=payload.merchant_id,
            amount=payload.amount,
            currency=payload.currency,
            customer_phone=payload.phone,
            customer_name=payload.customer_name,
            merchant_reference=payload.reference,
            description=payload.description,
        )
        message = (
            collection.get("failure_reason") or "This payment attempt failed."
            if collection["status"] == "failed"
            else "Selcom Pesa prompt sent. Please approve in your Selcom Pesa app."
        )
        body = {
            "collection_id": collection["id"],
            "reference": collection.get("merchant_reference"),
            "status": to_external_status(collection["status"]),
            "message": message,
        }
        return status.HTTP_202_ACCEPTED, body

    _status_code, body = await run_idempotent(
        client,
        merchant_id=payload.merchant_id,
        endpoint="POST /v1/collections/selcom-pesa",
        idempotency_key=idempotency_key,
        request_payload=payload.model_dump(mode="json"),
        handler=_handler,
    )
    return APIResponse(data=CollectionPushCreateResponse(**body))


@router.post("/qr", response_model=APIResponse[CollectionQrCreateResponse], status_code=status.HTTP_202_ACCEPTED)
async def create_qr_collection(
    payload: CollectionQrCreateRequest,
    caller: Annotated[AuthenticatedCaller, Depends(get_authenticated_caller)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
):
    """POS/counter/delivery scan-to-pay. `qr_payload`/`payment_token` are
    exactly what Selcom's own create-order-minimal response returned —
    this endpoint never generates a QR itself. Order creation succeeding
    means a QR/token now exists, **not** that anyone has paid — never
    mark an order paid from this response."""
    authorize_merchant_action(caller, payload.merchant_id, *_DASHBOARD_ROLES)
    require_api_key_scope(caller, "collections:write")
    client = get_supabase_admin()

    async def _handler() -> tuple[int, dict]:
        collection = await execute_qr_collection(
            client,
            merchant_id=payload.merchant_id,
            amount=payload.amount,
            currency=payload.currency,
            customer_phone=payload.customer_phone,
            customer_name=payload.customer_name,
            merchant_reference=payload.reference,
            description=payload.description,
        )
        body = {
            "collection_id": collection["id"],
            "reference": collection.get("merchant_reference"),
            "status": to_external_status(collection["status"]),
            "payment_token": collection.get("payment_token"),
            "qr_payload": collection.get("qr"),
            "expires_at": None,
        }
        return status.HTTP_202_ACCEPTED, body

    _status_code, body = await run_idempotent(
        client,
        merchant_id=payload.merchant_id,
        endpoint="POST /v1/collections/qr",
        idempotency_key=idempotency_key,
        request_payload=payload.model_dump(mode="json"),
        handler=_handler,
    )
    return APIResponse(data=CollectionQrCreateResponse(**body))


@router.get("/{collection_id}", response_model=APIResponse[CollectionStatusResponse])
def get_collection_status(
    collection_id: uuid.UUID,
    merchant_id: uuid.UUID,
    caller: Annotated[AuthenticatedCaller, Depends(get_authenticated_caller)],
):
    """`collection_id` may be the id returned by any of the four create
    endpoints above — including a payment_links id from POST
    /v1/collections, resolved to its real linked collection once the
    customer has picked a method (see
    app/services/collections_api.py::find_collection_by_external_id)."""
    authorize_merchant_action(caller, merchant_id, *_DASHBOARD_ROLES)
    require_api_key_scope(caller, "collections:read")
    client = get_supabase_admin()

    row = find_collection_by_external_id(client, merchant_id=merchant_id, external_id=collection_id)
    if not row:
        raise NotFoundError("Collection not found")
    return APIResponse(data=_status_response(row))


@router.post("/{collection_id}/refresh-status", response_model=APIResponse[CollectionStatusResponse])
async def refresh_collection_status(
    collection_id: uuid.UUID,
    merchant_id: uuid.UUID,
    caller: Annotated[AuthenticatedCaller, Depends(get_authenticated_caller)],
):
    """Queries Selcom directly and applies the same reversal-safe
    completion logic the webhook uses
    (app/services/checkout_reconciliation.py) — safe to call repeatedly,
    never double-credits or double-reverses. A no-op (returns the
    current state unchanged) if `collection_id` names a payment page
    with no method chosen yet — there's nothing to refresh."""
    authorize_merchant_action(caller, merchant_id, *_DASHBOARD_ROLES)
    require_api_key_scope(caller, "collections:write")
    client = get_supabase_admin()

    row = find_collection_by_external_id(client, merchant_id=merchant_id, external_id=collection_id)
    if not row:
        raise NotFoundError("Collection not found")

    if not row.get("checkout_order_id"):
        return APIResponse(data=_status_response(row))

    try:
        resolved = await refresh_checkout_collection_status(client, collection_id=uuid.UUID(row["id"]))
    except ConflictError:
        return APIResponse(data=_status_response(row))
    return APIResponse(data=_status_response(resolved))
