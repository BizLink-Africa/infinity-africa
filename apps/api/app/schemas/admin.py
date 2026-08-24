"""Response models for the platform-wide super-admin dashboard —
/v1/admin/* (app/routers/admin.py). Every model here adds a merchant_name
(or owner/actor name) join on top of an existing per-resource response
shape (see app/schemas/{merchants,payment_links,invoices,collections,
disbursements,transactions}.py) — these are read-only dashboard views, not
a replacement for those resource-oriented schemas.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class AdminOverviewResponse(BaseModel):
    total_merchants: int
    collections_today: Decimal
    withdrawals_today: Decimal
    active_payment_links: int
    paid_invoices_today: int
    outstanding_invoice_value: Decimal
    failed_transactions: int
    platform_revenue: Decimal
    pending_onboarding_requests: int
    pending_withdrawals: int


class AdminApiKeyResponse(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    merchant_name: str
    name: str
    environment: str
    key_prefix: str
    scopes: list[str]
    status: str
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime


class AdminMerchantResponse(BaseModel):
    merchant_id: uuid.UUID
    business_name: str
    owner_name: str | None = None
    email: str
    contact_phone: str | None = None
    nature_of_business: str | None = None
    physical_address: str | None = None
    account_status: str
    available_balance: Decimal
    created_at: datetime


class AdminMerchantUserResponse(BaseModel):
    user_id: uuid.UUID
    merchant_id: uuid.UUID
    merchant_name: str
    full_name: str | None = None
    email: str | None = None
    role: str
    status: str
    created_at: datetime


class AdminPaymentLinkResponse(BaseModel):
    link_id: uuid.UUID
    merchant_id: uuid.UUID
    merchant_name: str
    customer_name: str | None = None
    customer_phone: str | None = None
    amount: Decimal
    currency: str
    status: str
    expires_at: datetime | None = None
    created_at: datetime


class AdminInvoiceResponse(BaseModel):
    invoice_id: uuid.UUID
    invoice_number: str
    merchant_id: uuid.UUID
    merchant_name: str
    customer_name: str | None = None
    customer_phone: str | None = None
    total_amount: Decimal
    status: str
    due_date: date
    created_at: datetime


class AdminCollectionResponse(BaseModel):
    collection_id: uuid.UUID
    merchant_id: uuid.UUID
    merchant_name: str
    source: str | None = None
    method: str
    amount: Decimal
    currency: str
    fee_amount: Decimal | None = None
    net_amount: Decimal | None = None
    phone: str | None = None
    merchant_reference: str | None = None
    provider_reference: str | None = None
    api_key_id: uuid.UUID | None = None
    payment_link_id: uuid.UUID | None = None
    invoice_id: uuid.UUID | None = None
    status: str
    created_at: datetime
    # Selcom Checkout wallet-push fields — null for collections made via
    # the older selcom/ placeholder client.
    order_id: str | None = None
    provider_transid: str | None = None
    channel: str | None = None
    provider_payment_status: str | None = None
    failure_reason: str | None = None


class AdminWithdrawalResponse(BaseModel):
    withdrawal_id: uuid.UUID
    merchant_id: uuid.UUID
    merchant_name: str
    method: str
    amount: Decimal
    currency: str
    destination: str
    destination_code: str | None = None
    # Raw account/phone number — the frontend masks this for display
    # (see apps/web/src/lib/format.ts::maskAccountIdentifier); never masked
    # here, since masking is a presentation concern, not a data-access one.
    destination_identifier: str
    status: str
    requires_approval: bool
    provider_reference: str | None = None
    # Fee snapshot, so the approval queue can show total charges/reserved/
    # recipient-receives without a second lookup — see
    # app/schemas/withdrawals.py::FeeBreakdown for the full breakdown shape.
    total_charges: Decimal = Decimal(0)
    total_reserved_amount: Decimal | None = None
    recipient_net_amount: Decimal | None = None
    pricing_rule_id: uuid.UUID | None = None
    rejection_reason: str | None = None
    admin_status_reason: str | None = None
    created_at: datetime


class AdminTransactionResponse(BaseModel):
    transaction_id: uuid.UUID
    merchant_id: uuid.UUID
    merchant_name: str
    reference: str
    type: str
    method: str
    gross_amount: Decimal
    fee_amount: Decimal
    net_amount: Decimal
    currency: str
    status: str
    created_at: datetime


class AdminWebhookEventResponse(BaseModel):
    """Inbound provider callback log (public.selcom_webhook_events) — not
    the outbound merchant webhook deliveries table (webhook_events), which
    already has its own merchant-scoped list at
    GET /v1/merchants/{merchant_id}/webhooks."""

    webhook_event_id: uuid.UUID
    provider: str
    event_type: str
    reference: str
    processed_at: datetime | None = None
    created_at: datetime
    status: str
    processing_error: str | None = None


class AdminAuditLogResponse(BaseModel):
    audit_id: uuid.UUID
    actor: str | None = None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None = None
    metadata: dict[str, Any]
    ip_address: str | None = None
    created_at: datetime
