import sys

import pytest

from app.database import session as session_module
from tests.fakes import FakeSupabaseClient


@pytest.fixture
def fake_client(monkeypatch) -> FakeSupabaseClient:
    """A fresh in-memory Supabase client, patched into every already-imported
    module that did `from app.database.session import get_supabase_admin` —
    which is all of app/auth, app/routers, app/services. Sweeping every
    module means new routers/services need no test-side changes to pick it
    up automatically.
    """
    client = FakeSupabaseClient()
    original = session_module.get_supabase_admin

    for module in list(sys.modules.values()):
        if module is not None and getattr(module, "get_supabase_admin", None) is original:
            monkeypatch.setattr(module, "get_supabase_admin", lambda: client)

    return client
