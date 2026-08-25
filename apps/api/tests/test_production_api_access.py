"""Production (`live`) API key creation/rotation requires an approved,
KYC-verified merchant AND an explicit Super Admin enable — sandbox keys
are never gated. See app/services/api_access.py.
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


def _merchant_admin(fake_client, **merchant_overrides):
    merchant = create_merchant(fake_client, **merchant_overrides)
    merchant_id = uuid.UUID(merchant["id"])
    user_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, user_id, "MERCHANT_ADMIN")
    return merchant, merchant_id, user_id


def test_sandbox_key_creation_never_gated_even_for_an_unverified_merchant(fake_client):
    _merchant, _merchant_id, user_id = _merchant_admin(fake_client, status="pending", kyc_status="unverified")

    response = client.post(
        "/v1/merchant/api-keys",
        headers=auth_headers(user_id),
        json={"name": "Sandbox key", "environment": "sandbox", "scopes": ["collections:write"]},
    )
    assert response.status_code == 201, response.text


def test_live_key_creation_blocked_for_unapproved_merchant(fake_client):
    _merchant, _merchant_id, user_id = _merchant_admin(fake_client, status="pending", kyc_status="unverified")

    response = client.post(
        "/v1/merchant/api-keys",
        headers=auth_headers(user_id),
        json={"name": "Live key", "environment": "live", "scopes": ["collections:write"]},
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "production_access_restricted"


def test_live_key_creation_blocked_when_approved_but_not_yet_enabled_by_admin(fake_client):
    """status=active + kyc_status=verified alone isn't enough — the
    explicit Super Admin toggle is a separate, required gate."""
    _merchant, _merchant_id, user_id = _merchant_admin(fake_client, status="active", kyc_status="verified")

    response = client.post(
        "/v1/merchant/api-keys",
        headers=auth_headers(user_id),
        json={"name": "Live key", "environment": "live", "scopes": ["collections:write"]},
    )
    assert response.status_code == 403, response.text


def test_live_key_creation_succeeds_once_fully_approved_and_enabled(fake_client):
    _merchant, merchant_id, user_id = _merchant_admin(fake_client, status="active", kyc_status="verified")
    fake_client.table("merchants").update({"api_production_enabled": True}).eq("id", str(merchant_id)).execute()

    response = client.post(
        "/v1/merchant/api-keys",
        headers=auth_headers(user_id),
        json={"name": "Live key", "environment": "live", "scopes": ["collections:write"]},
    )
    assert response.status_code == 201, response.text
    assert response.json()["data"]["environment"] == "live"


def test_rotating_a_live_key_re_checks_production_access(fake_client):
    _merchant, merchant_id, user_id = _merchant_admin(fake_client, status="active", kyc_status="verified")
    fake_client.table("merchants").update({"api_production_enabled": True}).eq("id", str(merchant_id)).execute()

    _raw_key, key_row = make_api_key(fake_client, merchant_id, environment="live")

    # Access revoked after the key already existed.
    fake_client.table("merchants").update({"api_production_enabled": False}).eq("id", str(merchant_id)).execute()

    response = client.post(f"/v1/merchant/api-keys/{key_row['id']}/rotate", headers=auth_headers(user_id))
    assert response.status_code == 403, response.text


def test_admin_enable_production_access_then_key_creation_succeeds(fake_client):
    _merchant, merchant_id, user_id = _merchant_admin(fake_client, status="active", kyc_status="verified")
    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)

    enable_response = client.post(
        f"/v1/admin/merchants/{merchant_id}/api-access/enable-production", headers=auth_headers(admin_id)
    )
    assert enable_response.status_code == 200, enable_response.text
    assert enable_response.json()["data"]["api_production_enabled"] is True

    create_response = client.post(
        "/v1/merchant/api-keys",
        headers=auth_headers(user_id),
        json={"name": "Live key", "environment": "live", "scopes": ["collections:write"]},
    )
    assert create_response.status_code == 201, create_response.text


def test_admin_disable_production_access_blocks_further_live_keys(fake_client):
    _merchant, merchant_id, user_id = _merchant_admin(fake_client, status="active", kyc_status="verified")
    fake_client.table("merchants").update({"api_production_enabled": True}).eq("id", str(merchant_id)).execute()
    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)

    disable_response = client.post(
        f"/v1/admin/merchants/{merchant_id}/api-access/disable-production", headers=auth_headers(admin_id)
    )
    assert disable_response.status_code == 200, disable_response.text
    assert disable_response.json()["data"]["api_production_enabled"] is False

    create_response = client.post(
        "/v1/merchant/api-keys",
        headers=auth_headers(user_id),
        json={"name": "Live key", "environment": "live", "scopes": ["collections:write"]},
    )
    assert create_response.status_code == 403, create_response.text


def test_only_super_admin_can_toggle_production_access(fake_client):
    _merchant, merchant_id, _user_id = _merchant_admin(fake_client)
    response = client.post(
        f"/v1/admin/merchants/{merchant_id}/api-access/enable-production", headers=auth_headers(uuid.uuid4())
    )
    assert response.status_code == 403
