"""Inbound POST /v1/webhooks/selcom/checkout delivery shape — Selcom
Checkout's own webhook (distinct from app/schemas/webhooks.py's
SelcomWebhookPayload, which is the older, unconfirmed placeholder
product's guessed shape). Field names per the reconciliation task brief:
transid, order_id, reference, result, resultcode, channel, amount,
phone, payment_status — same "not yet confirmed against a real
delivery" caveat as app/services/selcom_checkout/parsing.py's
get-order-status parser; see that module's docstring.
"""

from pydantic import BaseModel


class SelcomCheckoutWebhookPayload(BaseModel):
    transid: str
    order_id: str
    reference: str
    result: str
    resultcode: str
    payment_status: str
    channel: str | None = None
    amount: str | None = None
    phone: str | None = None
