import uuid
from datetime import date, datetime

from pydantic import BaseModel


class DocumentRequestFileResponse(BaseModel):
    id: uuid.UUID
    request_id: uuid.UUID
    document_label: str
    original_filename: str
    mime_type: str
    size_bytes: int
    created_at: datetime


class DocumentRequestResponse(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    transaction_id: uuid.UUID | None = None
    alert_id: uuid.UUID | None = None
    requested_documents: list[str]
    reason: str
    status: str
    due_date: date | None = None
    created_at: datetime
    updated_at: datetime
    files: list[DocumentRequestFileResponse] = []


class AdminDocumentRequestResponse(BaseModel):
    """Admin list/detail view — id renamed to request_id and merchant_name
    joined on, matching every other Admin*Response in app/schemas/admin.py."""

    request_id: uuid.UUID
    merchant_id: uuid.UUID
    merchant_name: str | None = None
    transaction_id: uuid.UUID | None = None
    alert_id: uuid.UUID | None = None
    requested_documents: list[str]
    reason: str
    status: str
    due_date: date | None = None
    created_at: datetime
    updated_at: datetime
    files: list[DocumentRequestFileResponse] = []

    @classmethod
    def from_row(cls, row: dict, *, merchant_name: str | None) -> "AdminDocumentRequestResponse":
        return cls(request_id=row["id"], merchant_name=merchant_name, **{k: v for k, v in row.items() if k != "id"})


class DocumentRequestReviewInput(BaseModel):
    note: str | None = None
