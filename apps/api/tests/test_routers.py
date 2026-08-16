"""End-to-end router tests: real FastAPI routing + real auth dependencies +
real service/ledger logic, against the in-memory FakeSupabaseClient (see
tests/fakes.py, tests/conftest.py) instead of a real Supabase project.

Payment-link-specific tests live in test_payment_links.py, disbursement
tests in test_disbursements.py.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services.selcom.client import get_selcom_client
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
    monkeypatch.setenv("MOCK_PROVIDER_FAILURE_RATE", "0")
    monkeypatch.setenv("MOCK_PROVIDER_LATENCY_SECONDS", "0")
    get_settings.cache_clear()
    get_selcom_client.cache_clear()
    yield
    get_settings.cache_clear()
    get_selcom_client.cache_clear()


# --- auth plumbing ----------------------------------------------------------


def test_endpoint_without_token_is_401(fake_client):
    merchant = create_merchant(fake_client)
    response = client.get(f"/v1/merchants/{merchant['id']}")
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "unauthorized"


def test_non_member_cannot_access_merchant(fake_client):
    merchant = create_merchant(fake_client)
    outsider_id = uuid.uuid4()

    response = client.get(f"/v1/merchants/{merchant['id']}", headers=auth_headers(outsider_id))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_super_admin_can_create_and_get_any_merchant(fake_client):
    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)

    create_response = client.post(
        "/v1/merchants",
        headers=auth_headers(admin_id),
        json={"business_name": "New Biz", "contact_email": "new@biz.com"},
    )
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "pending"
    assert body["data"]["kyc_status"] == "unverified"

    merchant_id = body["data"]["id"]
    get_response = client.get(f"/v1/merchants/{merchant_id}", headers=auth_headers(admin_id))
    assert get_response.status_code == 200
    assert get_response.json()["data"]["business_name"] == "New Biz"


def test_merchant_admin_can_update_own_merchant_profile(fake_client):
    merchant = create_merchant(fake_client)
    admin_user_id = uuid.uuid4()
    make_merchant_member(fake_client, uuid.UUID(merchant["id"]), admin_user_id, "MERCHANT_ADMIN")

    response = client.patch(
        f"/v1/merchants/{merchant['id']}",
        headers=auth_headers(admin_user_id),
        json={"business_name": "Renamed Biz"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["business_name"] == "Renamed Biz"


def test_merchant_staff_cannot_update_merchant_profile(fake_client):
    """MERCHANT_STAFF gets read access but not the ADMIN-only profile write."""
    merchant = create_merchant(fake_client)
    staff_user_id = uuid.uuid4()
    make_merchant_member(fake_client, uuid.UUID(merchant["id"]), staff_user_id, "MERCHANT_STAFF")

    response = client.patch(
        f"/v1/merchants/{merchant['id']}",
        headers=auth_headers(staff_user_id),
        json={"business_name": "Renamed Biz"},
    )

    assert response.status_code == 403
