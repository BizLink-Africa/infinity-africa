"""Orchestrates the two-step Selcom Checkout Selcom Pesa flow
(create_order_minimal -> selcompesa_payment) for a customer paying a
public payment link via their Selcom Pesa wallet —
execute_selcompesa_push_for_payment_link(). Mirrors
app/services/wallet_push.py's execute_wallet_push_for_payment_link()
exactly, method-for-method — see that module's docstring for the full
reasoning; this one only differs in which Selcom endpoint actually
pushes (selcompesa_payment vs process_wallet_payment) and the
collections.method label stored (SELCOM_PESA_PUSH, already a valid
value in the collections.method CHECK constraint — no migration
needed).

**This module never credits a merchant, posts a ledger entry, or marks a
payment_link PAID.** Same rule as wallet_push.py: Selcom Pesa's push
response is normally PENDING — the real outcome is only known later, via
the webhook or a manual status refresh
(app/services/checkout_reconciliation.py, app/routers/webhooks.py).
"""

import uuid
from decimal import Decimal

from supabase import Client

from app.core.references import generate_reference
from app.core.time import utc_now_iso
from app.services.checkout_orders import get_or_create_checkout_order_for_payment_link
from app.services.collections import create_processing_transaction
from app.services.crud import execute_maybe_single
from app.services.crud import insert_row as _insert_row
from app.services.selcom_checkout.client import (
    SelcomCheckoutHTTPClient,
    get_selcom_checkout_credentials,
)

_METHOD_LABEL = "SELCOM_PESA_PUSH"


async def execute_selcompesa_push_for_payment_link(client: Client, *, payment_link: dict, buyer_phone: str) -> dict:
    """The one call site allowed to reach
    SelcomCheckoutHTTPClient.selcompesa_payment() — see that method's own
    docstring for why it must never be called speculatively or
    automatically.

    Idempotent beyond the router's Idempotency-Key header: if a push is
    already in flight or resolved for this payment link (via *either*
    Selcom Pesa or wallet-push — both are pushes to the same customer,
    so a second one while the first is still live would be a duplicate
    attempt, not a genuine retry), returns that existing collection
    instead of triggering a second real push. buyer_phone must already
    be normalized to "255XXXXXXXXX" by the caller.
    """
    payment_link_id = payment_link["id"]

    existing_collection = execute_maybe_single(
        client.table("collections")
        .select("*")
        .eq("payment_link_id", payment_link_id)
        .in_("status", ["processing", "successful"])
        .order("created_at", desc=True)
        .range(0, 0)
        .maybe_single()
    )
    if existing_collection:
        return existing_collection

    order = await get_or_create_checkout_order_for_payment_link(
        client, payment_link=payment_link, buyer_phone=buyer_phone
    )

    merchant_id = uuid.UUID(payment_link["merchant_id"])
    base_row = {
        "merchant_id": str(merchant_id),
        "payment_link_id": payment_link_id,
        "checkout_order_id": order["id"],
        "method": _METHOD_LABEL,
        "amount": str(payment_link["amount"]),
        "currency": payment_link["currency"],
        "customer_phone": buyer_phone,
        "provider": "selcom",
        "initiated_at": utc_now_iso(),
    }

    if order["status"] != "created":
        return _insert_row(
            client,
            "collections",
            {
                **base_row,
                "status": "failed",
                "failure_reason": "Could not create the payment order with the provider",
                "checkout_order_id": order["id"],
                "provider_resultcode": order.get("provider_result_code"),
                "provider_result": order.get("provider_result"),
                "provider_message": order.get("provider_message"),
                "raw_response": order.get("raw_response") or {},
            },
        )

    transid = generate_reference("TXN")
    checkout_client = SelcomCheckoutHTTPClient(credentials=get_selcom_checkout_credentials())
    result = await checkout_client.selcompesa_payment(transid=transid, order_id=order["order_id"], msisdn=buyer_phone)

    # Same convention as wallet_push.py: "successful"/"ambiguous" both
    # stay "processing" deliberately — only Selcom's own clearly-failed
    # codes move this to "failed".
    collection_status = "failed" if result.status == "failed" else "processing"

    collection = _insert_row(
        client,
        "collections",
        {
            **base_row,
            "status": collection_status,
            "failure_reason": result.message if collection_status == "failed" else None,
            "provider_reference": result.reference or None,
            "provider_transid": transid,
            "provider_resultcode": result.resultcode,
            "provider_result": result.result,
            "provider_message": result.message,
            "raw_response": result.raw_response,
        },
    )

    if collection_status == "processing":
        create_processing_transaction(
            client,
            merchant_id=merchant_id,
            method=_METHOD_LABEL,
            collection_id=collection["id"],
            provider_reference=result.reference or transid,
            amount=Decimal(str(payment_link["amount"])),
            currency=payment_link["currency"],
        )

    return collection
