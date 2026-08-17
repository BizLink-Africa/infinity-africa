"""Request/response schemas for the self-service /v1/merchant/* API surface
(app/routers/merchant_portal.py).

Every *Create schema here is a sibling of an existing one in
app/schemas/{payment_links,invoices,collections,disbursements}.py with
merchant_id removed — /v1/merchant/* never takes merchant_id from the
client at all, it's resolved from the caller's JWT (see
app.auth.get_own_merchant). Response shapes are reused as-is from those
modules wherever nothing about them is merchant_id-specific.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.phone import validate_and_normalize_phone
from app.schemas.enums import CollectionMethod, DestinationCode, DisbursementMethod
from app.schemas.invoices import InvoiceItemCreate
from app.schemas.merchants import MerchantResponse

# --- Overview ---------------------------------------------------------------


class MerchantOverviewResponse(BaseModel):
    merchant: MerchantResponse
    total_collections: Decimal
    available_balance: Decimal
    pending_transactions: int
    successful_withdrawals: int
    active_payment_links: int
    unpaid_invoices: int
    total_fees_charged: Decimal


# --- Payment links ------------------------------------------------------------


class MerchantPaymentLinkCreate(BaseModel):
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


class MerchantPaymentLinkUpdate(BaseModel):
    """Mirrors PaymentLinkUpdate (schemas/payment_links.py) minus merchant_id
    — same "only an ACTIVE link may be edited" rule, enforced in the router."""

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


# --- Invoices -----------------------------------------------------------------


class MerchantInvoiceCreate(BaseModel):
    customer_id: uuid.UUID | None = None
    customer_name: str | None = None
    customer_email: str | None = None
    customer_phone: str | None = None
    due_date: date
    currency: str = "TZS"
    tax_amount: Decimal = Field(default=Decimal(0), ge=0)
    discount_amount: Decimal = Field(default=Decimal(0), ge=0)
    notes: str | None = None
    items: list[InvoiceItemCreate] = Field(min_length=1)


# --- Collections ----------------------------------------------------------


class MerchantPushCollectionRequest(BaseModel):
    """USSD_PUSH / STK_PUSH / SELCOM_PESA_PUSH — a phone number is required."""

    amount: Decimal = Field(gt=0)
    currency: str = "TZS"
    customer_id: uuid.UUID | None = None
    customer_name: str | None = None
    customer_email: str | None = None
    customer_phone: str
    merchant_reference: str | None = Field(default=None, max_length=100)
    payment_link_id: uuid.UUID | None = None
    invoice_id: uuid.UUID | None = None
    description: str | None = None
    callback_url: str | None = None

    @field_validator("customer_phone")
    @classmethod
    def _check_phone(cls, value: str) -> str:
        return validate_and_normalize_phone(value)


class MerchantDynamicQrCollectionRequest(BaseModel):
    """DYNAMIC_QR — scan-based; no phone number needed."""

    amount: Decimal = Field(gt=0)
    currency: str = "TZS"
    customer_id: uuid.UUID | None = None
    customer_name: str | None = None
    customer_email: str | None = None
    customer_phone: str | None = None
    merchant_reference: str | None = Field(default=None, max_length=100)
    payment_link_id: uuid.UUID | None = None
    invoice_id: uuid.UUID | None = None
    description: str | None = None
    callback_url: str | None = None

    @field_validator("customer_phone")
    @classmethod
    def _check_phone(cls, value: str | None) -> str | None:
        return validate_and_normalize_phone(value) if value is not None else None


# --- Withdrawals (disbursements, user-facing name) -------------------------


class WithdrawalCreate(BaseModel):
    method: DisbursementMethod
    amount: Decimal = Field(gt=0)
    currency: str = "TZS"
    # Which provider the fee/pricing rule lookup and Selcom payout resolve
    # against (see app/services/withdrawals/fee_calculator.py) — required
    # so the fee actually charged always matches what the merchant saw on
    # the /quote call.
    destination_code: DestinationCode
    # A generic recipient display name — optional since the literal spec
    # only names bank_account_name (bank transfers); kept here too so a
    # phone-based withdrawal doesn't lose the name a merchant already typed
    # (the Merchant Portal withdrawal form collects one for every method).
    destination_name: str | None = None
    destination_phone: str | None = None
    # Optional, MOBILE_MONEY-only in practice — Selcom's real requirement
    # here is unverified (see app/services/selcom/withdrawals.py), so this
    # stays unvalidated rather than guessing a required/allowed-values list.
    network: str | None = None
    bank_name: str | None = None
    bank_account_number: str | None = None
    bank_account_name: str | None = None
    description: str | None = None

    @model_validator(mode="after")
    def _validate_destination(self) -> "WithdrawalCreate":
        if self.method == DisbursementMethod.BANK_ACCOUNT:
            if not self.bank_name or not self.bank_account_number:
                raise ValueError("bank_name and bank_account_number are required for BANK_ACCOUNT withdrawals")
        else:
            if not self.destination_phone:
                raise ValueError("destination_phone is required for this withdrawal method")
            self.destination_phone = validate_and_normalize_phone(self.destination_phone)
        return self

    @property
    def destination_identifier(self) -> str:
        return self.bank_account_number if self.method == DisbursementMethod.BANK_ACCOUNT else (self.destination_phone or "")

    @property
    def resolved_destination_name(self) -> str:
        """execute_disbursement() requires a destination_name for every
        method, but the withdrawal request only carries a name for
        BANK_ACCOUNT (bank_account_name) — for phone-based methods the
        phone number itself is the only identifying detail given, so it
        doubles as the display name."""
        if self.method == DisbursementMethod.BANK_ACCOUNT:
            return self.bank_account_name or self.bank_account_number or "Bank withdrawal"
        return self.destination_name or self.destination_phone or "Withdrawal"
