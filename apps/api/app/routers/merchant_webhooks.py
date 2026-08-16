"""Self-service webhook configuration — /v1/merchant/webhook-config* and
/v1/merchant/webhook-events.

merchants.webhook_url/webhook_secret already existed (services/webhooks.py's
enqueue_webhook_event reads them) but had no API surface for a merchant to
set them themselves. This adds that surface, plus a synchronous "send a test
delivery now" endpoint — deliberately separate from the real outbound queue
(webhook_events, status='pending'): no delivery/retry worker exists yet for
that queue (future work), so a test send is a direct, immediate HTTP POST
that reports its own result rather than pretending to be part of a delivery
pipeline that isn't built.
"""

import json
import time
import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends

from app.auth import require_own_merchant_role
from app.core.errors import ValidationAPIError
from app.core.pagination import PaginationParams, build_page_meta, pagination_params
from app.database.session import get_supabase_admin
from app.schemas.auth import MerchantMembership
from app.schemas.common import APIResponse
from app.schemas.enums import UserRole
from app.schemas.webhook_config import (
    WebhookConfigResponse,
    WebhookConfigUpdate,
    WebhookConfigUpdateResponse,
    WebhookEventResponse,
    WebhookTestResult,
)
from app.services.crud import get_by_id, list_for_merchant, update_row
from app.services.webhooks import sign_outbound_payload

router = APIRouter(prefix="/merchant", tags=["merchant-webhooks"])

_ADMIN_AND_STAFF = (UserRole.MERCHANT_ADMIN, UserRole.MERCHANT_STAFF)
_ADMIN_AND_DEVELOPER = (UserRole.MERCHANT_ADMIN, UserRole.DEVELOPER)

_SAMPLE_TEST_PAYLOAD = {
    "event": "collection.success",
    "test": True,
    "data": {
        "reference": "TXN-TEST0000",
        "amount": "1000.00",
        "currency": "TZS",
        "status": "successful",
    },
}


def _last_delivery(client, merchant_id: uuid.UUID) -> dict | None:
    """Most recent webhook_events row for this merchant, or None if it's
    never had one. Not .maybe_single() — that requires exactly 0 or 1 rows
    match, but a merchant can have many; order + take the first instead,
    same pattern as services/onboarding.py's list_onboarding_submissions."""
    rows = (
        client.table("webhook_events")
        .select("event_name, status, created_at")
        .eq("merchant_id", str(merchant_id))
        .order("created_at", desc=True)
        .execute()
    ).data or []
    return rows[0] if rows else None


@router.get("/webhook-config", response_model=APIResponse[WebhookConfigResponse])
def get_webhook_config(
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
):
    client = get_supabase_admin()
    merchant = get_by_id(client, "merchants", membership.merchant_id)
    return APIResponse(
        data=WebhookConfigResponse(
            webhook_url=merchant.get("webhook_url") if merchant else None,
            subscribed_events=merchant.get("webhook_subscribed_events") if merchant else None,
            has_secret=bool(merchant and merchant.get("webhook_secret")),
            last_delivery=_last_delivery(client, membership.merchant_id),
        )
    )


@router.patch("/webhook-config", response_model=APIResponse[WebhookConfigUpdateResponse])
def update_webhook_config(
    payload: WebhookConfigUpdate,
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_DEVELOPER))],
):
    client = get_supabase_admin()
    update_data: dict = {}
    if payload.webhook_url is not None:
        update_data["webhook_url"] = str(payload.webhook_url)
    if payload.subscribed_events is not None:
        update_data["webhook_subscribed_events"] = payload.subscribed_events

    new_secret: str | None = None
    if payload.regenerate_secret:
        new_secret = uuid.uuid4().hex + uuid.uuid4().hex  # 64 hex chars
        update_data["webhook_secret"] = new_secret

    merchant = update_row(client, "merchants", membership.merchant_id, update_data) if update_data else get_by_id(
        client, "merchants", membership.merchant_id
    )

    return APIResponse(
        data=WebhookConfigUpdateResponse(
            webhook_url=merchant.get("webhook_url") if merchant else None,
            subscribed_events=merchant.get("webhook_subscribed_events") if merchant else None,
            has_secret=bool(merchant and merchant.get("webhook_secret")),
            last_delivery=_last_delivery(client, membership.merchant_id),
            secret=new_secret,
        )
    )


@router.post("/webhook-config/test", response_model=APIResponse[WebhookTestResult])
def send_test_webhook(
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_DEVELOPER))],
):
    client = get_supabase_admin()
    merchant = get_by_id(client, "merchants", membership.merchant_id)
    webhook_url = merchant.get("webhook_url") if merchant else None
    webhook_secret = merchant.get("webhook_secret") if merchant else None

    if not webhook_url:
        raise ValidationAPIError("Configure a webhook URL before sending a test delivery")

    raw_body = json.dumps(_SAMPLE_TEST_PAYLOAD).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if webhook_secret:
        headers["X-Infinity-Signature"] = sign_outbound_payload(raw_body=raw_body, secret=webhook_secret)

    started = time.monotonic()
    try:
        response = httpx.post(webhook_url, content=raw_body, headers=headers, timeout=8.0)
        latency_ms = int((time.monotonic() - started) * 1000)
        return APIResponse(
            data=WebhookTestResult(delivered=response.is_success, http_status=response.status_code, latency_ms=latency_ms)
        )
    except httpx.HTTPError:
        latency_ms = int((time.monotonic() - started) * 1000)
        return APIResponse(data=WebhookTestResult(delivered=False, http_status=None, latency_ms=latency_ms))


@router.get("/webhook-events", response_model=APIResponse[list[WebhookEventResponse]])
def list_my_webhook_events(
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
):
    client = get_supabase_admin()
    rows, total = list_for_merchant(client, "webhook_events", merchant_id=membership.merchant_id, pagination=pagination)
    data = [WebhookEventResponse(**row) for row in rows]
    return APIResponse(data=data, meta=build_page_meta(pagination, total))
