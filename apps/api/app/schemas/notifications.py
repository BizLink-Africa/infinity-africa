import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: uuid.UUID
    recipient_type: str
    merchant_id: uuid.UUID | None = None
    notification_type: str
    title: str
    body: str
    related_resource_type: str | None = None
    related_resource_id: uuid.UUID | None = None
    is_read: bool
    created_at: datetime
