import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class RefundResponse(BaseModel):
    id: uuid.UUID
    dispute_id: uuid.UUID
    transaction_id: uuid.UUID
    merchant_id: uuid.UUID
    amount: Decimal
    currency: str
    status: str
    requested_by: str
    evidence_files: list[dict]
    provider_reference: str | None = None
    created_at: datetime
    updated_at: datetime


class RefundStatusUpdate(BaseModel):
    """Admin marks a refund's outcome based on provider/manual confirmation —
    there is no live payment-provider refund API integrated yet."""

    status: str
    provider_reference: str | None = None
