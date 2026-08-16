import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.enums import CollectionMethod


class PaymentLinkCreate(BaseModel):
    merchant_id: uuid.UUID
    customer_id: uuid.UUID | None = None
    amount: Decimal = Field(gt=0)
    currency: str = "TZS"
    customer_name: str | None = None
    customer_phone: str | None = None
    customer_email: str | None = None
    description: str | None = None
    allowed_payment_methods: list[CollectionMethod] = Field(default_factory=lambda: list(CollectionMethod))
    expires_at: datetime | None = None
    merchant_reference: str | None = Field(default=None, max_length=100)
    success_redirect_url: str | None = None
    failure_redirect_url: str | None = None


class PaymentLinkUpdate(BaseModel):
    """All fields optional — only ACTIVE links may be edited (routers.py
    enforces this; nothing about a PAID/EXPIRED/CANCELLED link's terms
    should change after the fact)."""

    amount: Decimal | None = Field(default=None, gt=0)
    currency: str | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    customer_email: str | None = None
    description: str | None = None
    allowed_payment_methods: list[CollectionMethod] | None = None
    expires_at: datetime | None = None
    merchant_reference: str | None = Field(default=None, max_length=100)
    success_redirect_url: str | None = None
    failure_redirect_url: str | None = None


class PaymentLinkResponse(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    customer_id: uuid.UUID | None = None
    amount: Decimal
    currency: str
    customer_name: str | None = None
    customer_phone: str | None = None
    customer_email: str | None = None
    description: str | None = None
    allowed_payment_methods: list[str]
    expires_at: datetime | None = None
    status: str
    public_slug: str
    public_url: str
    merchant_reference: str | None = None
    success_redirect_url: str | None = None
    failure_redirect_url: str | None = None
    paid_at: datetime | None = None
    attempt_count: int = 0
    created_at: datetime
    updated_at: datetime


class PublicPaymentLinkResponse(BaseModel):
    """What a customer sees on the checkout page — no merchant-internal
    fields (no id, merchant_id, customer_id, public_slug, merchant_reference,
    timestamps).

    Always 200s for a slug that exists, even when it's no longer payable —
    `status` tells the frontend which state (ACTIVE/EXPIRED/CANCELLED/PAID)
    to render, rather than a bare 404 that can't distinguish those cases.
    success_redirect_url/failure_redirect_url ARE included — the checkout
    page needs them to redirect the customer after a collection resolves.
    """

    merchant_name: str
    amount: Decimal
    currency: str
    description: str | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    expires_at: datetime | None = None
    allowed_payment_methods: list[str]
    status: str
    success_redirect_url: str | None = None
    failure_redirect_url: str | None = None


class PaymentLinkCollectRequest(BaseModel):
    method: CollectionMethod
    customer_phone: str | None = None
