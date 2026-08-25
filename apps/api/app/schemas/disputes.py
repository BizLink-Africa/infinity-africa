import re
import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

_PHONE_PATTERN = re.compile(r"\+?[0-9]{9,15}")


class PublicDisputeReportCreate(BaseModel):
    """POST /v1/public/disputes/report — no auth, so every field is
    caller-supplied and only loosely validated (a customer may not have the
    exact transaction reference to hand; this must never reject a genuine
    report over a formatting mismatch)."""

    customer_name: str
    customer_phone: str
    customer_email: str | None = None
    transaction_reference: str | None = None
    merchant_name: str | None = None
    amount: Decimal | None = None
    payment_date: date | None = None
    reason_category: str
    description: str

    @field_validator("customer_phone")
    @classmethod
    def _check_phone(cls, value: str) -> str:
        if not _PHONE_PATTERN.fullmatch(value):
            raise ValueError("must be a valid phone number (digits, optional leading +, 9-15 digits)")
        return value


class DisputeResponse(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID | None = None
    transaction_id: uuid.UUID | None = None
    customer_name: str
    customer_phone: str
    customer_email: str | None = None
    transaction_reference: str | None = None
    amount: Decimal | None = None
    reason_category: str
    description: str
    status: str
    evidence_files: list[dict]
    created_at: datetime
    updated_at: datetime


class AdminDisputeResponse(BaseModel):
    """Admin list/detail view — id renamed to dispute_id and merchant_name
    joined on, matching every other Admin*Response in app/schemas/admin.py."""

    dispute_id: uuid.UUID
    merchant_id: uuid.UUID | None = None
    merchant_name: str | None = None
    merchant_code: str | None = None
    transaction_id: uuid.UUID | None = None
    customer_name: str
    customer_phone: str
    customer_email: str | None = None
    transaction_reference: str | None = None
    amount: Decimal | None = None
    reason_category: str
    description: str
    status: str
    evidence_files: list[dict]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(
        cls, row: dict, *, merchant_name: str | None, merchant_code: str | None = None
    ) -> "AdminDisputeResponse":
        return cls(
            dispute_id=row["id"],
            merchant_name=merchant_name,
            merchant_code=merchant_code,
            **{k: v for k, v in row.items() if k != "id"},
        )


class DisputeMessageCreate(BaseModel):
    body: str = Field(min_length=1)


class DisputeMessageResponse(BaseModel):
    id: uuid.UUID
    dispute_id: uuid.UUID
    sender_type: str
    sender_id: uuid.UUID | None = None
    body: str
    attachment_files: list[dict]
    created_at: datetime


class DisputeStatusUpdate(BaseModel):
    status: str
    note: str | None = None


class RequestRefundInput(BaseModel):
    amount: Decimal = Field(gt=0)
