"""Translation + lookup layer for the external developer Collections API
(app/routers/collections_api.py). Two things live here, both because
this codebase's real internal shape doesn't map 1:1 onto what the
external API commits to:

1. Status/method translation (`to_external_status`/`to_external_method`)
   — the external API promises a fixed vocabulary
   (created/processing/pending_clearance/successful/failed/cancelled/
   reversed) that reads naturally to an integrator and won't change
   shape if internal implementation details do. The real internal
   collections.status values are pending/processing/successful/failed/
   reversed/cancelled/pending_review — translated 1:1 except
   pending -> created and pending_review -> pending_clearance.

   **pending_review is NOT a general "funds held during a clearance
   window" state** — it's a narrow hold used only when the payer's
   phone matches the merchant's own registered phone (self-payment/
   "own till" risk — see app/services/fraud_monitoring_service.py::
   check_self_payment_risk and docs/ledger-reconciliation.md). Mapping
   it to "pending_clearance" externally is the closest honest fit (both
   mean "provider signaled completion, but funds are not available yet,
   pending a review step") — it is not evidence that a universal
   delayed-settlement window exists for every collection. A normal
   (non-self-payment) collection still moves from processing straight to
   successful, same as every other collection method in this codebase —
   see docs/ledger-reconciliation.md's "Why full delayed clearance isn't
   wired up" section.

2. Dual-resource lookup (`find_collection_by_external_id`) — POST
   /v1/collections (the "Infinity Payment Page" flow) creates a
   `payment_links` row, not a `collections` row — no payment method has
   been chosen yet, so there's genuinely nothing in `collections` to
   point at. The other three creation endpoints (wallet-push/selcom-pesa/
   qr) create a real `collections` row immediately. GET/refresh-status
   need to accept whichever id a caller got back and resolve it
   correctly either way — including a payment_links id that *has since*
   grown a linked collection once the customer picked a method on the
   payment page, in which case that collection's real state is what's
   returned, not the link's own status.
"""

import uuid

from supabase import Client

from app.services.crud import execute_maybe_single, get_by_id

_STATUS_TO_EXTERNAL: dict[str, str] = {
    "pending": "created",
    "processing": "processing",
    "successful": "successful",
    "failed": "failed",
    "reversed": "reversed",
    "cancelled": "cancelled",
    "pending_review": "pending_clearance",
}

_METHOD_TO_EXTERNAL: dict[str, str] = {
    "STK_PUSH": "wallet_push",
    "SELCOM_PESA_PUSH": "selcom_pesa",
    "DYNAMIC_QR": "qr",
}


def to_external_status(internal_status: str) -> str:
    return _STATUS_TO_EXTERNAL.get(internal_status, internal_status)


def to_external_method(internal_method: str | None) -> str | None:
    if internal_method is None:
        return None
    return _METHOD_TO_EXTERNAL.get(internal_method, internal_method.lower())


def find_collection_by_external_id(client: Client, *, merchant_id: uuid.UUID, external_id: uuid.UUID) -> dict | None:
    """Returns the most authoritative row for this id: a real
    `collections` row if one exists (by id directly, or via
    `payment_link_id` if `external_id` names a payment_links row that
    has since grown one); otherwise a payment_links row shaped as a
    still-`created` synthetic collection view; otherwise None.

    Scoped to `merchant_id` throughout — an id belonging to a different
    merchant is treated as not found, same as every other merchant-scoped
    lookup in this codebase."""
    collection = get_by_id(client, "collections", external_id)
    if collection and collection["merchant_id"] == str(merchant_id):
        return collection

    link = get_by_id(client, "payment_links", external_id)
    if not link or link["merchant_id"] != str(merchant_id):
        return None

    linked_collection = execute_maybe_single(
        client.table("collections")
        .select("*")
        .eq("payment_link_id", str(external_id))
        .order("created_at", desc=True)
        .range(0, 0)
        .maybe_single()
    )
    if linked_collection:
        return linked_collection

    # No method chosen yet on the payment page — a synthetic "created"
    # view of the link itself, shaped like a collections row so the
    # router's response schema doesn't need a separate branch.
    return {
        "id": link["id"],
        "merchant_id": link["merchant_id"],
        "merchant_reference": link.get("merchant_reference"),
        "status": "pending",
        "amount": link["amount"],
        "currency": link["currency"],
        "method": None,
        "provider_payment_status": None,
        "failure_reason": None,
        "created_at": link["created_at"],
        "updated_at": link["updated_at"],
        "checkout_order_id": None,
    }
