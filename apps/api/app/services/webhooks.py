"""Webhook event enqueueing + incoming Selcom webhook storage.

enqueue_webhook_event only *records* an OUTBOUND event (public.webhook_events,
status='pending') — it does not deliver it. Actual HTTP delivery with
retries/signing is future work for a background worker; this is the write
side that worker would read from.

store_incoming_selcom_event is the other direction: logging an INBOUND
delivery from Selcom to POST /v1/webhooks/selcom, in public.selcom_webhook_events.
"""

import hashlib
import hmac
import uuid
from typing import Any

from supabase import Client

from app.services.crud import execute_maybe_single, get_by_id, insert_row


def sign_outbound_payload(*, raw_body: bytes, secret: str) -> str:
    """HMAC-SHA256 over the raw JSON body, using the merchant's own
    webhook_secret — the signature a merchant's receiving endpoint should
    recompute and compare to verify a delivery genuinely came from Infinity Africa.
    Same scheme as compute_selcom_signature, just the other direction."""
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


def find_selcom_webhook_event(client: Client, event_id: str) -> dict | None:
    query = (
        client.table("selcom_webhook_events")
        .select("*")
        .eq("provider", "selcom")
        .eq("event_id", event_id)
        .maybe_single()
    )
    return execute_maybe_single(query)


def store_incoming_selcom_event(
    client: Client,
    *,
    event_id: str,
    event_type: str,
    raw_body: str,
    signature: str | None,
    signature_valid: bool,
) -> tuple[dict, bool]:
    """Records an inbound Selcom webhook delivery. Returns (row, is_duplicate).

    (provider, event_id) is the idempotency key: checked first so a retried
    delivery of an event already stored short-circuits as a duplicate
    instead of reprocessing its side effects; the DB's own unique
    constraint is the backstop against a concurrent race on the same event.
    """
    existing = find_selcom_webhook_event(client, event_id)
    if existing:
        return existing, True

    try:
        row = insert_row(
            client,
            "selcom_webhook_events",
            {
                "provider": "selcom",
                "event_id": event_id,
                "event_type": event_type,
                "raw_body": raw_body,
                "signature": signature,
                "signature_valid": signature_valid,
                "status": "received",
            },
        )
    except Exception:
        existing = find_selcom_webhook_event(client, event_id)
        if existing:
            return existing, True
        raise

    return row, False


def enqueue_webhook_event(
    client: Client,
    *,
    merchant_id: uuid.UUID,
    event_name: str,
    payload: dict[str, Any],
) -> dict | None:
    """No-ops (returns None) if the merchant hasn't configured a webhook_url,
    or if they've opted into a subset of events via webhook_subscribed_events
    and this event_name isn't in it. Null/empty subscribed_events means
    "all events" — the default, unchanged behavior for merchants who never
    touch that setting."""
    merchant = get_by_id(client, "merchants", merchant_id)
    target_url = merchant.get("webhook_url") if merchant else None

    if not target_url:
        return None

    subscribed = merchant.get("webhook_subscribed_events") if merchant else None
    if subscribed and event_name not in subscribed:
        return None

    return insert_row(
        client,
        "webhook_events",
        {
            "merchant_id": str(merchant_id),
            "event_name": event_name,
            "payload": payload,
            "target_url": target_url,
            "status": "pending",
            "attempts": 0,
        },
    )
