"""Orchestrates the two-step Selcom Checkout wallet-push flow
(create_order_minimal -> process_wallet_payment) for a customer paying a
public payment link via mobile money push (STK/USSD/wallet pull).

**This module never credits a merchant, posts a ledger entry, or marks a
payment_link PAID.** Selcom's wallet-payment response is normally
PENDING (resultcode 111) — the real outcome is only known later, via an
async callback that isn't implemented yet (the task that adds this
explicitly defers it: "remaining blocker before webhook/status prompt").
Even in the rare case Selcom responds SUCCESS synchronously, this module
still only records that in `collections.provider_result`/
`provider_resultcode` for audit — the collection's own aggregate
`status` never advances past "processing" here, matching every other
push-based collection method's existing convention in this codebase
(see app/services/collections.py's LiveSelcomClient.initiate_collection
docstring: "A push always acks as processing — real resolution comes
from check_collection_status... or the webhook callback, never
synchronously from the push call itself"). Reaching collections.status
== "successful" anywhere else in this codebase implies ledger entries
were already posted (see resolve_collection()'s docstring) — this module
deliberately never creates that state, to avoid a collection that claims
success without any money having actually been credited.
"""

import uuid

from supabase import Client

from app.core.references import generate_reference
from app.core.time import utc_now_iso
from app.services.checkout_orders import get_or_create_checkout_order_for_payment_link
from app.services.crud import execute_maybe_single, insert_row
from app.services.selcom_checkout.client import (
    SelcomCheckoutHTTPClient,
    get_selcom_checkout_credentials,
)

# collections.method must be one of USSD_PUSH/STK_PUSH/SELCOM_PESA_PUSH/
# DYNAMIC_QR (DB CHECK constraint) — Selcom's wallet-payment call itself
# takes no method/channel parameter at all (only transid/order_id/msisdn;
# confirmed against the real endpoint contract), so Selcom picks the
# actual push channel server-side based on the msisdn's carrier. STK_PUSH
# is the closest existing label and matches this flow's own "approve
# using your PIN" customer-facing copy; it's a labeling simplification,
# not a claim that Selcom always uses STK specifically — worth revisiting
# if collections.method ever needs a genuinely channel-agnostic value.
_WALLET_PUSH_METHOD_LABEL = "STK_PUSH"


async def execute_wallet_push_for_payment_link(client: Client, *, payment_link: dict, buyer_phone: str) -> dict:
    """The one call site allowed to reach
    SelcomCheckoutHTTPClient.process_wallet_payment() — see that
    method's own docstring for why it must never be called
    speculatively or automatically.

    Idempotent beyond the router's Idempotency-Key header: if a push is
    already in flight or resolved for this payment link, returns that
    existing collection instead of triggering a second real push
    ("Do not allow duplicate credits" / "duplicate attempt does not
    double-credit" — the task's own requirement). buyer_phone must
    already be normalized to "255XXXXXXXXX" by the caller.
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
        "method": _WALLET_PUSH_METHOD_LABEL,
        "amount": str(payment_link["amount"]),
        "currency": payment_link["currency"],
        "customer_phone": buyer_phone,
        "provider": "selcom",
        "initiated_at": utc_now_iso(),
    }

    if order["status"] != "created":
        # The order shell itself failed at Selcom — nothing to push
        # against. Recorded as a failed collection attempt (not raised
        # as an error) so the customer sees a clear pending->failed
        # transition rather than a bare 500, and so this attempt is
        # visible for support/reconciliation like any other.
        return insert_row(
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
    result = await checkout_client.process_wallet_payment(
        transid=transid, order_id=order["order_id"], msisdn=buyer_phone
    )

    # "successful"/"ambiguous" both stay "processing" here deliberately
    # — see module docstring. Only Selcom's own clearly-failed codes move
    # this to "failed"; anything else (including an immediate SUCCESS)
    # waits for the not-yet-implemented webhook/reconciliation step.
    collection_status = "failed" if result.status == "failed" else "processing"

    return insert_row(
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
