import uuid
from datetime import datetime

from pydantic import BaseModel


class FraudAlertResponse(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    transaction_id: uuid.UUID | None = None
    customer_phone: str | None = None
    rule_code: str
    risk_level: str
    reason: str
    status: str
    metadata: dict
    created_at: datetime
    updated_at: datetime


class FraudAlertEventResponse(BaseModel):
    id: uuid.UUID
    alert_id: uuid.UUID
    actor_id: uuid.UUID | None = None
    actor_type: str
    action: str
    from_status: str | None = None
    to_status: str | None = None
    note: str | None = None
    created_at: datetime


class FraudAlertStatusUpdate(BaseModel):
    status: str
    note: str | None = None


class FraudAlertNoteCreate(BaseModel):
    note: str


class RequestDocumentsInput(BaseModel):
    requested_documents: list[str]
    reason: str
    due_date: str | None = None  # ISO date, e.g. "2026-08-30"


class AdminFraudAlertResponse(BaseModel):
    """Admin list/detail view — id renamed to alert_id and merchant_name
    joined on, matching every other Admin*Response in app/schemas/admin.py."""

    alert_id: uuid.UUID
    merchant_id: uuid.UUID
    merchant_name: str | None = None
    transaction_id: uuid.UUID | None = None
    customer_phone: str | None = None
    rule_code: str
    risk_level: str
    reason: str
    status: str
    metadata: dict
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: dict, *, merchant_name: str | None) -> "AdminFraudAlertResponse":
        return cls(alert_id=row["id"], merchant_name=merchant_name, **{k: v for k, v in row.items() if k != "id"})


class TransactionReviewResponse(BaseModel):
    id: uuid.UUID
    transaction_id: uuid.UUID
    merchant_id: uuid.UUID
    status: str
    latest_alert_id: uuid.UUID | None = None
    opened_at: datetime
    cleared_at: datetime | None = None
