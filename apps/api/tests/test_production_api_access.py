"""Self-service production (`live`) API key creation. Business decision
(amended 2026-08-26): production keys are self-service — no per-key or
per-merchant Super Admin approval — once a merchant is approved, KYC-
verified, has a resolvable pricing rule, and isn't API-access-suspended.
Sandbox keys are never gated (except by suspension). See
app/services/api_access.py.
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
    create_pricing_rule,
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


def _approved_merchant_with_pricing(fake_client, **merchant_overrides):
    merchant, merchant_id, user_id = _merchant_admin(
        fake_client, status="active", kyc_status="verified", **merchant_overrides
    )
    create_pricing_rule(fake_client, merchant_id=merchant_id)
    return merchant, merchant_id, user_id


def test_sandbox_key_creation_never_gated_even_for_an_unverified_merchant(fake_client):
    _merchant, _merchant_id, user_id = _merchant_admin(fake_client, status="pending", kyc_status="unverified")

    response = client.post(
        "/v1/merchant/api-keys",
        headers=auth_headers(user_id),
        json={"name": "Sandbox key", "environment": "sandbox", "scopes": ["collections:write"]},
    )
    assert response.status_code == 201, response.text


def test_live_key_creation_blocked_for_unapproved_merchant_with_exact_message(fake_client):
    _merchant, _merchant_id, user_id = _merchant_admin(fake_client, status="pending", kyc_status="unverified")

    response = client.post(
        "/v1/merchant/api-keys",
        headers=auth_headers(user_id),
        json={"name": "Live key", "environment": "live", "scopes": ["collections:write"]},
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "production_access_restricted"
    assert response.json()["error"]["message"] == (
        "Production API keys are available after your business account is approved."
    )


def test_live_key_creation_blocked_when_approved_but_no_pricing_rule_resolves(fake_client):
    """status=active + kyc_status=verified alone isn't enough — a pricing
    rule (merchant-specific or platform fallback) must also resolve. No
    Super Admin toggle exists anymore; this is the one remaining automatic
    check beyond approval/KYC."""
    _merchant, _merchant_id, user_id = _merchant_admin(fake_client, status="active", kyc_status="verified")

    response = client.post(
        "/v1/merchant/api-keys",
        headers=auth_headers(user_id),
        json={"name": "Live key", "environment": "live", "scopes": ["collections:write"]},
    )
    assert response.status_code == 403, response.text


def test_live_key_creation_succeeds_self_service_once_approved_verified_and_priced(fake_client):
    """No Super Admin action of any kind is required here — this is the
    core self-service behavior change."""
    _merchant, _merchant_id, user_id = _approved_merchant_with_pricing(fake_client)

    response = client.post(
        "/v1/merchant/api-keys",
        headers=auth_headers(user_id),
        json={"name": "Live key", "environment": "live", "scopes": ["collections:write"]},
    )
    assert response.status_code == 201, response.text
    assert response.json()["data"]["environment"] == "live"


def test_live_key_creation_succeeds_via_platform_fallback_pricing_rule(fake_client):
    _merchant, _merchant_id, user_id = _merchant_admin(fake_client, status="active", kyc_status="verified")
    create_pricing_rule(fake_client, merchant_id=None)  # platform fallback, no merchant-specific rule

    response = client.post(
        "/v1/merchant/api-keys",
        headers=auth_headers(user_id),
        json={"name": "Live key", "environment": "live", "scopes": ["collections:write"]},
    )
    assert response.status_code == 201, response.text


def test_rotating_a_live_key_re_checks_eligibility(fake_client):
    _merchant, merchant_id, user_id = _approved_merchant_with_pricing(fake_client)
    _raw_key, key_row = make_api_key(fake_client, merchant_id, environment="live")

    # Eligibility revoked after the key already existed.
    fake_client.table("merchants").update({"status": "suspended"}).eq("id", str(merchant_id)).execute()

    response = client.post(f"/v1/merchant/api-keys/{key_row['id']}/rotate", headers=auth_headers(user_id))
    assert response.status_code == 403, response.text


def test_suspended_merchant_cannot_self_service_a_sandbox_or_live_key(fake_client):
    _merchant, _merchant_id, user_id = _approved_merchant_with_pricing(fake_client, api_access_suspended=True)

    for environment in ("sandbox", "live"):
        response = client.post(
            "/v1/merchant/api-keys",
            headers=auth_headers(user_id),
            json={"name": f"{environment} key", "environment": environment, "scopes": ["collections:write"]},
        )
        assert response.status_code == 403, response.text


def test_super_admin_suspend_blocks_further_self_service_key_creation(fake_client):
    _merchant, merchant_id, user_id = _approved_merchant_with_pricing(fake_client)
    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)

    suspend_response = client.post(
        f"/v1/admin/merchants/{merchant_id}/api-access/suspend", headers=auth_headers(admin_id)
    )
    assert suspend_response.status_code == 200, suspend_response.text
    assert suspend_response.json()["data"]["api_access_suspended"] is True

    create_response = client.post(
        "/v1/merchant/api-keys",
        headers=auth_headers(user_id),
        json={"name": "Live key", "environment": "live", "scopes": ["collections:write"]},
    )
    assert create_response.status_code == 403, create_response.text


def test_super_admin_reinstate_restores_self_service_key_creation(fake_client):
    _merchant, merchant_id, user_id = _approved_merchant_with_pricing(fake_client, api_access_suspended=True)
    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)

    reinstate_response = client.post(
        f"/v1/admin/merchants/{merchant_id}/api-access/reinstate", headers=auth_headers(admin_id)
    )
    assert reinstate_response.status_code == 200, reinstate_response.text
    assert reinstate_response.json()["data"]["api_access_suspended"] is False

    create_response = client.post(
        "/v1/merchant/api-keys",
        headers=auth_headers(user_id),
        json={"name": "Live key", "environment": "live", "scopes": ["collections:write"]},
    )
    assert create_response.status_code == 201, create_response.text


def test_only_super_admin_can_suspend_api_access(fake_client):
    _merchant, merchant_id, _user_id = _merchant_admin(fake_client)
    response = client.post(
        f"/v1/admin/merchants/{merchant_id}/api-access/suspend", headers=auth_headers(uuid.uuid4())
    )
    assert response.status_code == 403


def test_admin_merchant_response_reports_computed_production_eligibility(fake_client):
    _merchant, merchant_id, _user_id = _approved_merchant_with_pricing(fake_client)
    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)

    response = client.get(f"/v1/admin/merchants/{merchant_id}", headers=auth_headers(admin_id))
    assert response.status_code == 200, response.text
    assert response.json()["data"]["production_api_eligible"] is True
