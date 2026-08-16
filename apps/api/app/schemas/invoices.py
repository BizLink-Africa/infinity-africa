import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class InvoiceItemCreate(BaseModel):
    description: str
    quantity: Decimal = Field(default=Decimal(1), gt=0)
    unit_price: Decimal = Field(ge=0)
    sort_order: int = 0


class InvoiceItemResponse(BaseModel):
    id: uuid.UUID
    description: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal
    sort_order: int


class InvoiceCreate(BaseModel):
    merchant_id: uuid.UUID
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


class InvoiceUpdate(BaseModel):
    """All fields optional — only what's provided is changed. Only allowed
    while the invoice is still DRAFT (see app/routers/invoices.py); once
    SENT, its amounts are what the customer was shown."""

    customer_id: uuid.UUID | None = None
    customer_name: str | None = None
    customer_email: str | None = None
    customer_phone: str | None = None
    due_date: date | None = None
    tax_amount: Decimal | None = Field(default=None, ge=0)
    discount_amount: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None
    items: list[InvoiceItemCreate] | None = Field(default=None, min_length=1)


class InvoiceResponse(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    customer_id: uuid.UUID | None = None
    invoice_number: str
    customer_name: str | None = None
    customer_email: str | None = None
    customer_phone: str | None = None
    due_date: date
    currency: str
    subtotal: Decimal
    tax_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    amount_paid: Decimal
    status: str
    payment_link_id: uuid.UUID | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    items: list[InvoiceItemResponse] = Field(default_factory=list)
