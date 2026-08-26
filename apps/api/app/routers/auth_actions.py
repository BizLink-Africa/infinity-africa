"""Account-level actions that need to run server-side rather than calling
Supabase directly from the browser — currently just forgot-password. Public
(unauthenticated) by nature: the caller doesn't have a session yet.
"""

from fastapi import APIRouter

from app.config import get_settings
from app.database.session import get_supabase_admin
from app.schemas.auth import ForgotPasswordRequest
from app.schemas.common import APIResponse
from app.services.email import send_password_reset_email

router = APIRouter(prefix="/auth", tags=["auth"])

# The one message this endpoint ever returns, regardless of whether the
# email matched a real account, whether a Supabase Auth error occurred, or
# whether Resend rejected the send — account enumeration prevention only
# works if every outcome looks identical from the outside.
_GENERIC_MESSAGE = "If an account exists, we've sent password reset instructions."


@router.post("/forgot-password", response_model=APIResponse[dict])
def forgot_password(payload: ForgotPasswordRequest):
    """Never raises, never returns a different message for a registered
    vs. unregistered email — send_password_reset_email already swallows
    every failure internally (missing account, Supabase error, Resend
    error) and returns None either way; this endpoint doesn't even look at
    what it returned."""
    client = get_supabase_admin()
    settings = get_settings()
    send_password_reset_email(client, email=payload.email, redirect_to=f"{settings.app_url}{payload.redirect_path}")
    return APIResponse(data={"message": _GENERIC_MESSAGE})
