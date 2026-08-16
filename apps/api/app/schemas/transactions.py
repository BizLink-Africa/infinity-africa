import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class TransactionResponse(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    reference: str
    provider_reference: str | None = None
    type: str
    method: str
    collection_id: uuid.UUID | None = None
    disbursement_id: uuid.UUID | None = None
    gross_amount: Decimal
    fee_amount: Decimal
    net_amount: Decimal
    currency: str
    status: str
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
