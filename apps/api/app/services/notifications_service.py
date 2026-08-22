"""In-app notifications — no delivery mechanism existed before this
feature; see supabase/migrations/20260817110000_notifications.sql. A thin
write-side wrapper called from fraud alert creation, document requests,
dispute submission, refund requests, and dispute status changes;
app/routers/merchant_portal.py and app/routers/admin_risk.py expose the
read side (GET /v1/merchant/notifications, GET /v1/admin/notifications).
"""

import uuid

from supabase import Client

from app.schemas.enums import NotificationType
from app.services.crud import insert_row


def notify_merchant(
    client: Client,
    *,
    merchant_id: uuid.UUID,
    notification_type: NotificationType,
    title: str,
    body: str,
    related_resource_type: str | None = None,
    related_resource_id: uuid.UUID | None = None,
) -> None:
    insert_row(
        client,
        "notifications",
        {
            "recipient_type": "merchant",
            "merchant_id": str(merchant_id),
            "notification_type": notification_type.value,
            "title": title,
            "body": body,
            "related_resource_type": related_resource_type,
            "related_resource_id": str(related_resource_id) if related_resource_id else None,
        },
    )


def notify_admin(
    client: Client,
    *,
    notification_type: NotificationType,
    title: str,
    body: str,
    related_resource_type: str | None = None,
    related_resource_id: uuid.UUID | None = None,
) -> None:
    insert_row(
        client,
        "notifications",
        {
            "recipient_type": "admin",
            "merchant_id": None,
            "notification_type": notification_type.value,
            "title": title,
            "body": body,
            "related_resource_type": related_resource_type,
            "related_resource_id": str(related_resource_id) if related_resource_id else None,
        },
    )
