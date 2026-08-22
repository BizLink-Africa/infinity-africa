import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class CheckoutOrderResponse(BaseModel):
    """A row of public.checkout_orders — the order shell created by
    Selcom Checkout's Create Order - Minimal endpoint. See
    supabase/migrations/20260822180000_checkout_orders.sql and
    app/services/checkout_orders.py."""

    id: uuid.UUID
    merchant_id: uuid.UUID
    payment_link_id: uuid.UUID | None = None

    order_id: str
    merchant_reference: str | None = None

    buyer_email: str
    buyer_name: str
    buyer_phone: str
    amount: Decimal
    currency: str
    buyer_remarks: str | None = None
    merchant_remarks: str | None = None
    no_of_items: int

    status: str

    provider: str
    provider_reference: str | None = None
    gateway_buyer_uuid: str | None = None
    payment_token: str | None = None
    qr: str | None = None
    payment_gateway_url: str | None = None

    provider_result_code: str | None = None
    provider_result: str | None = None
    provider_message: str | None = None

    initiated_at: datetime
    created_at: datetime
    updated_at: datetime
