"""Checkout order lifecycle — currently just Step 1: create the order
shell via Selcom Checkout's Create Order - Minimal
(https://developers.selcommobile.com/#create-order-minimal). Never pulls
money — see app/services/selcom_checkout/client.py's module docstring.

order_id sent to Selcom is server-generated (generate_reference("ORD")),
never client-supplied — guarantees uniqueness rather than trusting it,
and is enforced again at the database level
(checkout_orders_merchant_order_id_key) as defense-in-depth. Callers use
merchant_reference for their own tracking value instead (same role as
collections.merchant_reference).

HTTP-level idempotency (retried requests replaying the same result
without re-calling Selcom) is handled by the router via
app.services.idempotency.run_idempotent, same as
POST /v1/merchant/withdrawals — not duplicated here.
"""

import uuid
from decimal import Decimal

from supabase import Client

from app.core.references import generate_reference
from app.core.time import utc_now_iso
from app.services.crud import insert_row
from app.services.selcom_checkout.client import (
    SelcomCheckoutHTTPClient,
    get_selcom_checkout_credentials,
)


async def create_checkout_order_minimal(
    client: Client,
    *,
    merchant_id: uuid.UUID,
    buyer_email: str,
    buyer_name: str,
    buyer_phone: str,
    amount: Decimal,
    currency: str,
    no_of_items: int,
    buyer_remarks: str | None = None,
    merchant_remarks: str | None = None,
    payment_link_id: uuid.UUID | None = None,
    merchant_reference: str | None = None,
) -> dict:
    """Calls Selcom, then persists the full result (success or not) to
    checkout_orders regardless of outcome — mirrors disbursements.py's
    convention of always keeping the raw provider response for
    support/reconciliation, not just on success.

    buyer_phone must already be normalized to "255XXXXXXXXX" by the
    caller's request schema (see CreateOrderMinimalRequest) — this
    function trusts it's already in that shape."""
    order_id = generate_reference("ORD")

    checkout_client = SelcomCheckoutHTTPClient(credentials=get_selcom_checkout_credentials())
    result = await checkout_client.create_order_minimal(
        order_id=order_id,
        buyer_email=buyer_email,
        buyer_name=buyer_name,
        buyer_phone=buyer_phone,
        amount=str(amount),
        currency=currency,
        no_of_items=no_of_items,
        buyer_remarks=buyer_remarks,
        merchant_remarks=merchant_remarks,
    )

    return insert_row(
        client,
        "checkout_orders",
        {
            "merchant_id": str(merchant_id),
            "payment_link_id": str(payment_link_id) if payment_link_id else None,
            "order_id": order_id,
            "merchant_reference": merchant_reference,
            "buyer_email": buyer_email,
            "buyer_name": buyer_name,
            "buyer_phone": buyer_phone,
            "amount": str(amount),
            "currency": currency,
            "buyer_remarks": buyer_remarks,
            "merchant_remarks": merchant_remarks,
            "no_of_items": no_of_items,
            "status": "created" if result.is_success else "failed",
            "provider": "selcom",
            "provider_reference": result.reference or None,
            "gateway_buyer_uuid": result.gateway_buyer_uuid,
            "payment_token": result.payment_token,
            "qr": result.qr,
            "payment_gateway_url": result.payment_gateway_url,
            "provider_result_code": result.resultcode,
            "provider_result": result.result,
            "provider_message": result.message,
            "raw_response": result.raw_response,
            "initiated_at": utc_now_iso(),
        },
    )
