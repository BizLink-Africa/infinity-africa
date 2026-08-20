"""GET /v1/system/selcom-config-status: super-admin gated, safe booleans
only — never the actual configured secret values.
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
    make_merchant_member,
    make_super_admin,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    # Isolate from whatever a developer's local apps/api/.env happens to
    # have set (e.g. real Selcom sandbox credentials) — this suite must
    # assert against a known state, not whatever's ambient on this machine.
    # A blank os.environ value (not just an absent one) is required to win
    # over apps/api/.env: pydantic-settings' source priority is init >
    # environment variables > dotenv file, so delenv alone still falls
    # through to a real value present in the dotenv file. Individual tests
    # override what they need via monkeypatch.setenv.
    for var in (
        "SELCOM_BASE_URL",
        "SELCOM_API_KEY",
        "SELCOM_API_SECRET",
        "SELCOM_VENDOR_ID",
        "SELCOM_MODE",
        "SELCOM_BUSINESS_API_KEY",
        "SELCOM_BUSINESS_PRIVATE_KEY_BASE64",
        "SELCOM_BUSINESS_ACCOUNT_NUMBER",
    ):
        monkeypatch.setenv(var, "")
    for bool_var in ("SELCOM_COLLECTION_ENABLED", "SELCOM_WITHDRAWAL_ENABLED"):
        monkeypatch.setenv(bool_var, "false")
    # SELCOM_BUSINESS_MODE isn't blanked like the others above — its
    # non-blank default ("sandbox") is itself part of what
    # test_selcom_config_status_all_false_when_unconfigured asserts.
    monkeypatch.setenv("SELCOM_BUSINESS_MODE", "sandbox")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_selcom_config_status_requires_auth(fake_client):
    response = client.get("/v1/system/selcom-config-status")
    assert response.status_code == 401


def test_selcom_config_status_rejects_non_admin(fake_client):
    merchant = create_merchant(fake_client)
    user_id = uuid.uuid4()
    make_merchant_member(fake_client, uuid.UUID(merchant["id"]), user_id, "MERCHANT_ADMIN")

    response = client.get("/v1/system/selcom-config-status", headers=auth_headers(user_id))
    assert response.status_code == 403


def test_selcom_config_status_returns_only_safe_booleans(fake_client, monkeypatch):
    monkeypatch.setenv("SELCOM_BASE_URL", "https://apigwtest.selcommobile.com")
    monkeypatch.setenv("SELCOM_API_KEY", "real-secret-key-should-never-appear-in-response")
    monkeypatch.setenv("SELCOM_API_SECRET", "real-secret-value-should-never-appear-in-response")
    monkeypatch.setenv("SELCOM_VENDOR_ID", "TILL12345")
    monkeypatch.setenv("SELCOM_COLLECTION_ENABLED", "true")
    monkeypatch.setenv("SELCOM_MODE", "live")
    monkeypatch.setenv("SELCOM_BUSINESS_MODE", "sandbox")
    monkeypatch.setenv("SELCOM_BUSINESS_API_KEY", "real-business-key-should-never-appear-in-response")
    monkeypatch.setenv("SELCOM_BUSINESS_PRIVATE_KEY_BASE64", "real-private-key-should-never-appear-in-response")
    monkeypatch.setenv("SELCOM_BUSINESS_ACCOUNT_NUMBER", "0000000000")
    get_settings.cache_clear()

    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)

    response = client.get("/v1/system/selcom-config-status", headers=auth_headers(admin_id))
    assert response.status_code == 200, response.text

    body = response.json()["data"]
    assert body == {
        "collection_enabled": True,
        "withdrawal_enabled": False,
        "mock_mode": False,
        "base_url_configured": True,
        "api_key_configured": True,
        "api_secret_configured": True,
        "vendor_id_configured": True,
        "business_mode": "sandbox",
        "business_api_key_configured": True,
        "business_private_key_configured": True,
        "business_account_number_configured": True,
    }

    raw_text = response.text
    assert "real-secret-key-should-never-appear-in-response" not in raw_text
    assert "real-secret-value-should-never-appear-in-response" not in raw_text
    assert "real-business-key-should-never-appear-in-response" not in raw_text
    assert "real-private-key-should-never-appear-in-response" not in raw_text
    assert "apigwtest.selcommobile.com" not in raw_text
    assert "TILL12345" not in raw_text
    assert "0000000000" not in raw_text

    get_settings.cache_clear()


def test_selcom_config_status_all_false_when_unconfigured(fake_client):
    get_settings.cache_clear()
    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)

    response = client.get("/v1/system/selcom-config-status", headers=auth_headers(admin_id))
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["base_url_configured"] is False
    assert body["api_key_configured"] is False
    assert body["api_secret_configured"] is False
    assert body["vendor_id_configured"] is False
    assert body["mock_mode"] is True
    assert body["business_mode"] == "sandbox"
    assert body["business_api_key_configured"] is False
    assert body["business_private_key_configured"] is False
    assert body["business_account_number_configured"] is False
