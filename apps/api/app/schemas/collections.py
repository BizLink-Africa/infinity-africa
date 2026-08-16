import re
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

_PHONE_PATTERN = re.compile(r"\+?[0-9]{9,15}")


def _validate_phone(value: str) -> str:
    if not _PHONE_PATTERN.fullmatch(value):
        raise ValueError("must be a valid phone number (digits, optional leading +, 9-15 digits)")
    return value


class CollectionInitiateBase(BaseModel):
    """Shared fields across all four /v1/collections/{method} endpoints.
    `method` itself isn't a field here — it's implied by which endpoint is
    called, so there's no way to send a method that doesn't match the URL."""

    merchant_id: uuid.UUID
    amount: Decimal = Field(gt=0)
    currency: str = "TZS"
    customer_id: uuid.UUID | None = None
    customer_name: str | None = None
    customer_email: str | None = None
    merchant_reference: str | None = Field(default=None, max_length=100)
    payment_link_id: uuid.UUID | None = None
    invoice_id: uuid.UUID | None = None
    description: str | None = None
    callback_url: str | None = None


class PushCollectionRequest(CollectionInitiateBase):
    """USSD_PUSH / STK_PUSH / SELCOM_PESA_PUSH — pushed to a phone, so a
    phone number is required."""

    customer_phone: str

    @field_validator("customer_phone")
    @classmethod
    def _check_phone(cls, value: str) -> str:
        return _validate_phone(value)


class DynamicQrCollectionRequest(CollectionInitiateBase):
    """DYNAMIC_QR — scan-based; no phone number needed."""

    customer_phone: str | None = None

    @field_validator("customer_phone")
    @classmethod
    def _check_phone(cls, value: str | None) -> str | None:
        return _validate_phone(value) if value is not None else None


class CollectionResponse(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    customer_id: uuid.UUID | None = None
    payment_link_id: uuid.UUID | None = None
    invoice_id: uuid.UUID | None = None
    merchant_reference: str | None = None
    method: str
    amount: Decimal
    currency: str
    customer_phone: str | None = None
    status: str
    provider: str | None = None
    provider_reference: str | None = None
    # Convenience fields threaded in by the router from data already
    # available at initiation time (the linked transaction row, a static
    # per-method message) — not columns of the collections table itself.
    transaction_reference: str | None = None
    message: str | None = None
    expires_at: datetime | None = None
    initiated_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DynamicQrCollectionResponse(CollectionResponse):
    qr_payload: str
    qr_expires_at: datetime
    # Always null today — no real QR image rendering exists in this
    # codebase yet (the frontend's QrPlaceholder is an explicit dev
    # placeholder, not derived from qr_payload). Populate once a real
    # Selcom response is observed to actually return one.
    qr_image_url: str | None = None
