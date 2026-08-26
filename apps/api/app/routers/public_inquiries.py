"""Public "contact us" inquiries — apps/web's marketing-site contact form
(components/landing/contact-form.tsx). Unauthenticated by nature; anyone
can submit one.
"""

from fastapi import APIRouter

from app.database.session import get_supabase_admin
from app.schemas.common import APIResponse
from app.schemas.inquiries import InquiryCreate
from app.services.crud import insert_row
from app.services.email import send_inquiry_notification_email

router = APIRouter(prefix="/public/inquiries", tags=["inquiries (public)"])


@router.post("", response_model=APIResponse[dict])
def create_inquiry(payload: InquiryCreate):
    """Saves the inquiry first, then best-effort notifies the CEO — a
    failed notification email must never lose the inquiry itself
    (send_inquiry_notification_email never raises, but this still wraps
    it for defense in depth, matching the same pattern used everywhere
    else a courtesy email sits next to a real write)."""
    client = get_supabase_admin()
    row = insert_row(
        client,
        "inquiries",
        {
            "full_name": payload.full_name,
            "business_name": payload.business_name,
            "email": payload.email,
            "phone": payload.phone,
            "message": payload.message,
            "source": payload.source,
        },
    )

    try:
        send_inquiry_notification_email(client, inquiry=row)
    except Exception:  # noqa: BLE001, S110 — best-effort, never loses the saved inquiry
        pass

    return APIResponse(data={"message": "Thanks — we've received your message and will be in touch soon."})
