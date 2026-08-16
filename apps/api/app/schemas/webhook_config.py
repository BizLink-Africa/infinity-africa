import uuid
from datetime import datetime

from pydantic import BaseModel, HttpUrl


class LastWebhookDelivery(BaseModel):
    event_name: str
    status: str
    created_at: datetime


class WebhookConfigResponse(BaseModel):
    webhook_url: str | None
    subscribed_events: list[str] | None
    has_secret: bool
    last_delivery: LastWebhookDelivery | None = None


class WebhookConfigUpdate(BaseModel):
    webhook_url: HttpUrl | None = None
    subscribed_events: list[str] | None = None
    regenerate_secret: bool = False


class WebhookConfigUpdateResponse(WebhookConfigResponse):
    """Same as WebhookConfigResponse, plus the plaintext secret — present
    only in the one response immediately after regenerate_secret=True, never
    retrievable again afterward (only used to sign outbound deliveries)."""

    secret: str | None = None


class WebhookTestResult(BaseModel):
    delivered: bool
    http_status: int | None
    latency_ms: int


class WebhookEventResponse(BaseModel):
    id: uuid.UUID
    event_name: str
    payload: dict
    target_url: str
    status: str
    attempts: int
    last_attempted_at: datetime | None = None
    delivered_at: datetime | None = None
    response_status_code: int | None = None
    created_at: datetime
