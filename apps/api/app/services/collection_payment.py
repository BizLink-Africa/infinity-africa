"""The unified customer-facing payment-method dispatcher — one function
both the public payment-link "pay" endpoint and (via the same
payment_links row Merchant Portal's "Request Collection" now creates,
see app/routers/merchant_portal.py) the merchant-initiated collection
flow route through. Three active methods, each already proven safe on
its own (none of them ever credits synchronously — see each module's own
docstring for why):

    WALLET_PUSH  -> app/services/wallet_push.py (Push STK/USSD/mobile
                    money, existing, proven end-to-end)
    SELCOM_PESA  -> app/services/selcompesa_push.py (new, mirrors
                    wallet_push.py exactly)
    TANQR        -> app/services/dynamic_qr.py (existing — "TanQR" is
                    this codebase's external name for what's stored
                    internally as collections.method = 'DYNAMIC_QR';
                    same product, same create-order-minimal-only flow,
                    no migration needed since DYNAMIC_QR was already a
                    valid collections.method value)

HOSTED_CHECKOUT is deliberately not in this dispatcher — it stays
reachable only via its own dedicated endpoint
(POST /public/payment-links/{slug}/pay/checkout), itself gated behind
settings.hosted_checkout_enabled (default False). See
docs/selcom-checkout-collections.md's "Known issue" section for why.

Every branch below returns the same normalized shape so the router
doesn't need method-specific handling: collection_id, status
("pending"/"failed"), message, and the QR/token fields (None when not
applicable to the method) — TanQR's qr/payment_token/payment_gateway_url
come straight from the checkout_orders row Selcom returned, exactly as
stored (see app/services/checkout_orders.py — never regenerated,
never altered).
"""

from typing import Literal

from supabase import Client

from app.core.phone import normalize_tz_phone
from app.services.dynamic_qr import execute_dynamic_qr_for_payment_link
from app.services.selcompesa_push import execute_selcompesa_push_for_payment_link
from app.services.wallet_push import execute_wallet_push_for_payment_link

CollectionPaymentMethod = Literal["WALLET_PUSH", "SELCOM_PESA", "TANQR"]

_PUSH_METHOD_MESSAGES: dict[str, str] = {
    "WALLET_PUSH": "Payment prompt sent. Please approve on your phone.",
    "SELCOM_PESA": "Selcom Pesa prompt sent. Please approve in your Selcom Pesa app.",
}


async def initiate_collection_payment(
    client: Client,
    *,
    payment_link: dict,
    method: CollectionPaymentMethod,
    customer_phone: str | None = None,
) -> dict:
    """Dispatches to the method-specific initiation function and
    normalizes the result. `customer_phone` is required (and normalized
    here, once, for both push methods) for WALLET_PUSH/SELCOM_PESA — a
    push has nowhere to go without one; optional for TANQR (falls back
    to the payment link's own customer_phone or a placeholder, same as
    execute_dynamic_qr_for_payment_link already does)."""
    if method in ("WALLET_PUSH", "SELCOM_PESA"):
        if not customer_phone:
            raise ValueError(f"{method} requires customer_phone")
        buyer_phone = normalize_tz_phone(customer_phone)

        if method == "WALLET_PUSH":
            collection = await execute_wallet_push_for_payment_link(
                client, payment_link=payment_link, buyer_phone=buyer_phone
            )
        else:
            collection = await execute_selcompesa_push_for_payment_link(
                client, payment_link=payment_link, buyer_phone=buyer_phone
            )

        payment_status = "failed" if collection["status"] == "failed" else "pending"
        message = (
            collection.get("failure_reason") or collection.get("provider_message") or "This payment attempt failed."
            if payment_status == "failed"
            else _PUSH_METHOD_MESSAGES[method]
        )
        return {
            "collection_id": collection["id"],
            "method": method,
            "status": payment_status,
            "message": message,
            "qr": None,
            "payment_token": None,
            "payment_gateway_url": None,
        }

    # TANQR
    collection = await execute_dynamic_qr_for_payment_link(
        client, payment_link=payment_link, customer_phone=customer_phone
    )
    payment_status = "failed" if collection["status"] == "failed" else "pending"
    message = (
        collection.get("failure_reason") or "Could not create the payment order with the provider"
        if payment_status == "failed"
        else "Scan this QR using your supported payment app."
    )
    return {
        "collection_id": collection["id"],
        "method": "TANQR",
        "status": payment_status,
        "message": message,
        "qr": collection.get("qr"),
        "payment_token": collection.get("payment_token"),
        "payment_gateway_url": collection.get("payment_gateway_url"),
    }
