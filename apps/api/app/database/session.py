"""Database session / Supabase client setup.

No ORM/models yet — no persistence has been built beyond the auth layer.
`get_supabase_admin()` below is the one piece implemented so far: a
service_role Supabase client used by app/auth to look up role membership
and API keys directly against the tables in supabase/migrations.
"""

from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings


@lru_cache
def get_supabase_admin() -> Client:
    """Server-only Supabase client authenticated as service_role.

    This bypasses Row Level Security entirely, which is exactly why it may
    only ever be constructed here, in the backend. SUPABASE_SERVICE_ROLE_KEY
    must never be set in apps/web's environment or sent to a browser.
    """
    settings = get_settings()

    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are not configured")

    return create_client(settings.supabase_url, settings.supabase_service_role_key)
