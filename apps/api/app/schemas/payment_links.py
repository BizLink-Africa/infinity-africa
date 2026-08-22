import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.core.phone import validate_and_normalize_phone
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


class PaymentLinkWalletPushRequest(BaseModel):
    """POST /public/payment-links/{public_slug}/pay/wallet-push — the
    Selcom Checkout create-order-minimal -> wallet-payment flow (Push
    STK/USSD/mobile money). customer_phone is required here (unlike
    PaymentLinkCollectRequest.customer_phone) — a push has nowhere to go
    without one."""

    customer_phone: str

    @field_validator("customer_phone")
    @classmethod
    def _check_phone(cls, value: str) -> str:
        return validate_and_normalize_phone(value)


class PaymentLinkWalletPushResponse(BaseModel):
    """What the customer's browser gets back — deliberately never
    reports "paid"/"successful", regardless of what Selcom's own
    resultcode said: Selcom's wallet-payment response is normally
    PENDING, and this backend doesn't yet resolve it further (see
    app/services/wallet_push.py's module docstring). payment_status is
    "failed" when the attempt genuinely failed outright (bad phone
    number, order-creation error) — a customer waiting on a push that's
    never coming deserves to know that — and "pending" for every other
    outcome, including an immediate SUCCESS."""

    collection_id: uuid.UUID
    payment_status: str
    message: str
