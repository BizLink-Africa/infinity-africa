import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.core.phone import validate_and_normalize_phone
from app.schemas.enums import LEGACY_ALLOWED_PAYMENT_METHODS_DEFAULT, CollectionMethod


class PaymentLinkCreate(BaseModel):
    merchant_id: uuid.UUID
    customer_id: uuid.UUID | None = None
    amount: Decimal = Field(gt=0)
    currency: str = "TZS"
    customer_name: str | None = None
    customer_phone: str | None = None
    customer_email: str | None = None
    description: str | None = None
    # No longer collected from the merchant — every payment link now
    # always offers the single "Pay securely" hosted-checkout flow. Kept
    # nullable/defaulted only for backward compatibility with old rows
    # and any external API caller still sending it explicitly.
    allowed_payment_methods: list[CollectionMethod] = Field(
        default_factory=lambda: list(LEGACY_ALLOWED_PAYMENT_METHODS_DEFAULT)
    )
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
    """What the customer's browser gets back from the initial submit —
    deliberately never reports "paid"/"successful" here even if Selcom's
    wallet-payment call happened to respond SUCCESS synchronously (rare):
    the real outcome is only trusted once the webhook or a status refresh
    confirms it (app/services/checkout_reconciliation.py). payment_status
    is "failed" when the attempt failed outright at submission (bad phone
    number, order-creation error) and "pending" for every other outcome.
    Use GET .../collections/{collection_id}/status (below) to poll for
    the real, eventual outcome — this response is just the immediate
    submission result."""

    collection_id: uuid.UUID
    payment_status: str
    message: str


class PaymentLinkCheckoutRequest(BaseModel):
    """POST /public/payment-links/{public_slug}/pay/checkout — the single
    "Pay securely" flow (2026-08-23): no channel to choose, always
    redirects to Selcom's own hosted checkout. customer_phone is
    optional here — only asked for on Infinity's page if the payment
    link doesn't already have one on file (see
    app/services/hosted_checkout.py's placeholder-phone fallback)."""

    customer_phone: str | None = None

    @field_validator("customer_phone")
    @classmethod
    def _check_phone(cls, value: str | None) -> str | None:
        return validate_and_normalize_phone(value) if value is not None else None


class PaymentLinkCheckoutResponse(BaseModel):
    """What the customer's browser gets back — payment_gateway_url is
    already base64-decoded (never sent as the raw base64 Selcom
    returns); the frontend does a full-page redirect to it, no polling
    on Infinity's side, since the customer leaves this site entirely."""

    collection_id: uuid.UUID
    payment_gateway_url: str | None = None


class PublicCollectionStatusResponse(BaseModel):
    """GET /public/payment-links/{public_slug}/collections/{collection_id}/status
    — polled by the customer payment page after a wallet-push submission.
    `status` is one of "pending" | "completed" | "failed" | "cancelled" |
    "user_cancelled" | "rejected", derived from the collection's own
    status plus Selcom's reported payment_status (never the payment
    link's status, which only ever reflects PAID once, not per-attempt
    detail)."""

    status: str
    message: str
