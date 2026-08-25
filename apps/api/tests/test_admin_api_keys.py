"""Platform-wide Super Admin API key views — GET/PATCH /v1/admin/api-keys*.

Real data only: every row here traces back to a genuine api_keys row
seeded via the same make_api_key() helper the rest of the suite uses —
nothing generated or mocked.
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
    make_super_admin,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_list_requires_super_admin(fake_client):
    response = client.get("/v1/admin/api-keys", headers=auth_headers(uuid.uuid4()))
    assert response.status_code == 403


def test_list_shows_keys_across_every_merchant(fake_client):
    merchant_a = create_merchant(fake_client, business_name="Amani Traders")
    merchant_b = create_merchant(fake_client, business_name="Salome Shop")
    make_api_key(fake_client, uuid.UUID(merchant_a["id"]), environment="live")
    make_api_key(fake_client, uuid.UUID(merchant_b["id"]), environment="sandbox")

    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)
    response = client.get("/v1/admin/api-keys", headers=auth_headers(admin_id))

    assert response.status_code == 200, response.text
    rows = response.json()["data"]
    assert len(rows) == 2
    merchant_names = {row["merchant_name"] for row in rows}
    assert merchant_names == {"Amani Traders", "Salome Shop"}
    for row in rows:
        assert "hashed_key" not in row


def test_list_filters_by_merchant_status_and_environment(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    _raw_live, _live_key = make_api_key(fake_client, merchant_id, environment="live")
    _raw_sandbox, sandbox_key = make_api_key(fake_client, merchant_id, environment="sandbox")
    sandbox_key["status"] = "revoked"

    other_merchant = create_merchant(fake_client)
    make_api_key(fake_client, uuid.UUID(other_merchant["id"]), environment="live")

    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)

    by_merchant = client.get(
        f"/v1/admin/api-keys?merchant_id={merchant_id}", headers=auth_headers(admin_id)
    )
    assert len(by_merchant.json()["data"]) == 2

    by_status = client.get("/v1/admin/api-keys?status=revoked", headers=auth_headers(admin_id))
    assert [row["id"] for row in by_status.json()["data"]] == [sandbox_key["id"]]

    by_env = client.get("/v1/admin/api-keys?environment=sandbox", headers=auth_headers(admin_id))
    assert [row["id"] for row in by_env.json()["data"]] == [sandbox_key["id"]]


def test_revoke_marks_key_revoked_regardless_of_owning_merchant(fake_client):
    merchant = create_merchant(fake_client)
    _raw_key, key_row = make_api_key(fake_client, uuid.UUID(merchant["id"]))

    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)
    response = client.patch(f"/v1/admin/api-keys/{key_row['id']}/revoke", headers=auth_headers(admin_id))

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "revoked"
    assert data["revoked_at"] is not None


def test_revoke_404s_for_unknown_key(fake_client):
    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)
    response = client.patch(f"/v1/admin/api-keys/{uuid.uuid4()}/revoke", headers=auth_headers(admin_id))
    assert response.status_code == 404


def test_super_admin_never_sees_the_full_secret_only_prefix_and_last4(fake_client):
    merchant = create_merchant(fake_client)
    raw_key, key_row = make_api_key(fake_client, uuid.UUID(merchant["id"]), ip_whitelist_enabled=True)

    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)
    response = client.get("/v1/admin/api-keys", headers=auth_headers(admin_id))

    assert response.status_code == 200, response.text
    row = next(r for r in response.json()["data"] if r["id"] == key_row["id"])
    assert raw_key not in response.text
    assert "plaintext_key" not in row
    assert "hashed_key" not in row
    assert row["key_prefix"] == key_row["key_prefix"]
    assert row["key_last4"] == raw_key[-4:]
    assert row["ip_whitelist_enabled"] is True
