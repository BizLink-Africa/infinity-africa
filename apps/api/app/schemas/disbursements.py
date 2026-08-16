import re
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

_PHONE_PATTERN = re.compile(r"\+?[0-9]{9,15}")


class DisbursementInitiateBase(BaseModel):
    """Shared fields across all three /v1/disbursements/{method} endpoints.
    `method` itself isn't a field here — it's implied by which endpoint is
    called, so there's no way to send a method that doesn't match the URL."""

    merchant_id: uuid.UUID
    amount: Decimal = Field(gt=0)
    currency: str = "TZS"
    destination_name: str


class PhoneDisbursementRequest(DisbursementInitiateBase):
    """SELCOM_PESA / MOBILE_MONEY — paid out to a phone number."""

    destination_identifier: str

    @field_validator("destination_identifier")
    @classmethod
    def _check_phone(cls, value: str) -> str:
        if not _PHONE_PATTERN.fullmatch(value):
            raise ValueError("must be a valid phone number (digits, optional leading +, 9-15 digits)")
        return value


class BankAccountDisbursementRequest(DisbursementInitiateBase):
    """BANK_ACCOUNT — destination_identifier is the bank account number."""

    destination_identifier: str
    bank_name: str


class DisbursementResponse(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    settlement_account_id: uuid.UUID | None = None
    method: str
    amount: Decimal
    currency: str
    destination_name: str
    destination_identifier: str
    bank_name: str | None = None
    status: str
    requires_approval: bool
    approved_by: uuid.UUID | None = None
    approved_at: datetime | None = None
    provider_reference: str | None = None
    # Response-only enrichment stamped on by services/disbursements.py once
    # a transaction exists — null while a high-value withdrawal still sits
    # PENDING approval, since nothing's been reserved yet.
    transaction_reference: str | None = None
    fee_amount: Decimal | None = None
    net_amount: Decimal | None = None
    initiated_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
