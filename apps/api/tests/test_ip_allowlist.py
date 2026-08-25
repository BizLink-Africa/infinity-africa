"""IP allowlist — merchant CRUD, Super Admin approve/reject, and live-only
enforcement in app.auth.dependencies.verify_api_key.

Enforcement tests probe with GET /v1/collections/{id}?merchant_id=...
using a random, non-existent collection id — verify_api_key's IP check
runs as a dependency *before* the route handler, so a 403 there means
the request never got past authentication, while a 404 ("Collection not
found") proves the IP check passed and the request reached real route
logic. Requests set X-Forwarded-For explicitly throughout, rather than
relying on TestClient's default client host, so the test controls
exactly which IP verify_api_key sees.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from tests.factories import (
    TEST_JWT_SECRET,
    auth_headers,
    create_merchant,
    make_api_key,
    make_merchant_member,
    make_super_admin,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _merchant_admin(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    user_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, user_id, "MERCHANT_ADMIN")
    return merchant_id, user_id


def _activate_allowlist_entry(fake_client, merchant_id, *, environment="live", ip="41.222.10.5"):
    return fake_client.seed(
        "api_ip_allowlist",
        {
            "merchant_id": str(merchant_id),
            "api_key_id": None,
            "environment": environment,
            "label": "Main server",
            "ip_address_or_cidr": ip,
            "status": "active",
            "notes": None,
            "created_by": None,
            "approved_by": None,
        },
    )


def _probe(raw_key: str, merchant_id: uuid.UUID, ip: str):
    """Any API-key-authenticated GET — the exact route doesn't matter,
    only whether verify_api_key's IP check lets the request through to
    real route logic (404, unknown collection id) or rejects it first
    (403)."""
    return client.get(
        f"/v1/collections/{uuid.uuid4()}?merchant_id={merchant_id}",
        headers={"X-API-Key": raw_key, "X-Forwarded-For": ip},
    )


def test_merchant_can_create_and_list_ip_allowlist_entries(fake_client):
    _merchant_id, user_id = _merchant_admin(fake_client)

    create_response = client.post(
        "/v1/merchant/ip-allowlist",
        headers=auth_headers(user_id),
        json={"environment": "live", "label": "Main server", "ip_address_or_cidr": "41.222.10.5"},
    )
    assert create_response.status_code == 201, create_response.text
    assert create_response.json()["data"]["status"] == "pending"

    list_response = client.get("/v1/merchant/ip-allowlist", headers=auth_headers(user_id))
    assert len(list_response.json()["data"]) == 1


def test_merchant_can_delete_own_entry_but_not_another_merchants(fake_client):
    merchant_a_id, user_a = _merchant_admin(fake_client)
    _merchant_b_id, user_b = _merchant_admin(fake_client)
    entry = _activate_allowlist_entry(fake_client, merchant_a_id)

    cross_delete = client.delete(f"/v1/merchant/ip-allowlist/{entry['id']}", headers=auth_headers(user_b))
    assert cross_delete.status_code == 404

    own_delete = client.delete(f"/v1/merchant/ip-allowlist/{entry['id']}", headers=auth_headers(user_a))
    assert own_delete.status_code == 200


def test_invalid_ip_or_cidr_is_rejected(fake_client):
    _merchant_id, user_id = _merchant_admin(fake_client)
    response = client.post(
        "/v1/merchant/ip-allowlist",
        headers=auth_headers(user_id),
        json={"environment": "live", "label": "Bad", "ip_address_or_cidr": "not-an-ip"},
    )
    assert response.status_code == 422


def test_admin_can_approve_a_pending_entry(fake_client):
    _merchant_id, user_id = _merchant_admin(fake_client)
    create_response = client.post(
        "/v1/merchant/ip-allowlist",
        headers=auth_headers(user_id),
        json={"environment": "live", "label": "Main server", "ip_address_or_cidr": "41.222.10.5"},
    )
    entry_id = create_response.json()["data"]["id"]

    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)
    approve_response = client.post(f"/v1/admin/ip-allowlist/{entry_id}/approve", headers=auth_headers(admin_id))
    assert approve_response.status_code == 200, approve_response.text
    assert approve_response.json()["data"]["status"] == "active"
    assert approve_response.json()["data"]["merchant_name"]


def test_a_key_with_ip_whitelisting_off_is_unrestricted_even_with_active_rows(fake_client):
    """Part 6: IP whitelisting is a per-key opt-in choice — having active
    allowlist rows configured (e.g. for a different key) doesn't restrict a
    key that chose "continue without IP whitelisting"."""
    merchant_id, _user_id = _merchant_admin(fake_client)
    _activate_allowlist_entry(fake_client, merchant_id, ip="41.222.10.5")
    raw_key, _key_row = make_api_key(fake_client, merchant_id, environment="live", ip_whitelist_enabled=False)

    response = _probe(raw_key, merchant_id, "1.2.3.4")
    assert response.status_code == 404  # reached real route logic, just no such collection


def test_ip_whitelist_enabled_but_no_active_rows_fails_closed(fake_client):
    """The opposite gap: a key that opted IN to IP whitelisting but has no
    approved IP yet must not be treated as unrestricted."""
    merchant_id, _user_id = _merchant_admin(fake_client)
    raw_key, _key_row = make_api_key(fake_client, merchant_id, environment="live", ip_whitelist_enabled=True)

    response = _probe(raw_key, merchant_id, "1.2.3.4")
    assert response.status_code == 403, response.text


def test_live_request_from_a_non_allowed_ip_is_rejected(fake_client):
    merchant_id, _user_id = _merchant_admin(fake_client)
    _activate_allowlist_entry(fake_client, merchant_id, ip="41.222.10.5")
    raw_key, _key_row = make_api_key(fake_client, merchant_id, environment="live", ip_whitelist_enabled=True)

    response = _probe(raw_key, merchant_id, "9.9.9.9")
    assert response.status_code == 403, response.text

    logs = fake_client.table("api_request_logs")._table.rows
    assert len(logs) == 1
    assert logs[0]["status_code"] == 403
    assert logs[0]["ip_address"] == "9.9.9.9"


def test_live_request_from_an_allowed_ip_succeeds(fake_client):
    merchant_id, _user_id = _merchant_admin(fake_client)
    _activate_allowlist_entry(fake_client, merchant_id, ip="41.222.10.5")
    raw_key, _key_row = make_api_key(fake_client, merchant_id, environment="live", ip_whitelist_enabled=True)

    response = _probe(raw_key, merchant_id, "41.222.10.5")
    assert response.status_code == 404  # passed the IP check


def test_cidr_range_matches(fake_client):
    merchant_id, _user_id = _merchant_admin(fake_client)
    _activate_allowlist_entry(fake_client, merchant_id, ip="41.222.10.0/24")
    raw_key, _key_row = make_api_key(fake_client, merchant_id, environment="live", ip_whitelist_enabled=True)

    response = _probe(raw_key, merchant_id, "41.222.10.200")
    assert response.status_code == 404


def test_sandbox_requests_are_never_ip_restricted(fake_client):
    merchant_id, _user_id = _merchant_admin(fake_client)
    _activate_allowlist_entry(fake_client, merchant_id, environment="sandbox", ip="41.222.10.5")
    raw_key, _key_row = make_api_key(fake_client, merchant_id, environment="sandbox", ip_whitelist_enabled=True)

    response = _probe(raw_key, merchant_id, "9.9.9.9")
    assert response.status_code == 404  # sandbox is never IP-restricted, even with the flag on


def test_last_used_ip_is_recorded_and_visible_to_super_admin(fake_client):
    merchant_id, _user_id = _merchant_admin(fake_client)
    raw_key, key_row = make_api_key(fake_client, merchant_id, environment="live")

    _probe(raw_key, merchant_id, "77.66.55.44")

    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)
    response = client.get("/v1/admin/api-keys", headers=auth_headers(admin_id))
    row = next(r for r in response.json()["data"] if r["id"] == key_row["id"])
    assert row["last_used_ip"] == "77.66.55.44"


def test_admin_api_logs_endpoint_shows_the_request(fake_client):
    merchant_id, _user_id = _merchant_admin(fake_client)
    raw_key, _key_row = make_api_key(fake_client, merchant_id, environment="live")
    _probe(raw_key, merchant_id, "77.66.55.44")

    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)
    response = client.get("/v1/admin/api-logs", headers=auth_headers(admin_id))
    rows = response.json()["data"]
    assert len(rows) == 1
    assert rows[0]["ip_address"] == "77.66.55.44"
    assert rows[0]["status_code"] == 404
    assert rows[0]["merchant_name"]
