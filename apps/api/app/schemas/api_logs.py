"""One row per API-key-authenticated HTTP request — /v1/merchant/api-logs
and, joined with merchant_name, /v1/admin/api-logs. See
app/middleware/api_request_log.py for how these are written."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class ApiRequestLogResponse(BaseModel):
    id: uuid.UUID
    api_key_id: uuid.UUID | None = None
    environment: str
    method: str
    path: str
    status_code: int
    ip_address: str | None = None
    duration_ms: int | None = None
    created_at: datetime


class AdminApiRequestLogResponse(ApiRequestLogResponse):
    merchant_id: uuid.UUID
    merchant_name: str
    merchant_code: str | None = None
