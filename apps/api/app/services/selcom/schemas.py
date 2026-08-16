"""Shared result types every Selcom client implementation (mock_client.py,
live_client.py) returns — the vocabulary the rest of the app (routers,
app/services/collections.py, app/services/disbursements.py) is written
against, regardless of which client is active. See client.py for the
PaymentProvider interface these types appear in.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ProviderStatus = Literal["successful", "failed", "processing"]


class CollectionResult(BaseModel):
    provider: str
    provider_reference: str
    status: ProviderStatus
    failure_reason: str | None = None


class DynamicQrResult(BaseModel):
    provider: str
    provider_reference: str
    qr_payload: str
    qr_expires_at: datetime


class DisbursementResult(BaseModel):
    provider: str
    provider_reference: str
    status: ProviderStatus
    failure_reason: str | None = None
