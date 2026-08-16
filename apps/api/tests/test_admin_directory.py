"""GET /v1/admin/merchants and /v1/admin/merchant-users — end to end
against the in-memory FakeSupabaseClient.
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
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_list_admin_merchants_requires_super_admin(fake_client):
    response = client.get("/v1/admin/merchants", headers=auth_headers(uuid.uuid4()))
    assert response.status_code == 403


def test_list_admin_merchants_includes_owner_name_and_balance(fake_client):
    merchant = create_merchant(fake_client, business_name="Kilimanjaro Fresh Produce")
    owner_id = uuid.uuid4()
    make_merchant_member(fake_client, uuid.UUID(merchant["id"]), owner_id, "MERCHANT_ADMIN")
    fake_client.seed_auth_user(owner_id, email="owner@example.com", full_name="Jane Doe")

    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)
    response = client.get("/v1/admin/merchants", headers=auth_headers(admin_id))
    assert response.status_code == 200
    row = response.json()["data"][0]
    assert row["business_name"] == "Kilimanjaro Fresh Produce"
    assert row["owner_name"] == "Jane Doe"
    assert row["available_balance"] == "0"
    assert row["account_status"] == "active"


def test_list_admin_merchants_owner_name_none_when_lookup_fails(fake_client):
    merchant = create_merchant(fake_client)
    make_merchant_member(fake_client, uuid.UUID(merchant["id"]), uuid.uuid4(), "MERCHANT_ADMIN")

    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)
    response = client.get("/v1/admin/merchants", headers=auth_headers(admin_id))
    assert response.status_code == 200
    assert response.json()["data"][0]["owner_name"] is None


def test_list_admin_merchant_users_joins_merchant_name(fake_client):
    merchant = create_merchant(fake_client, business_name="Amani Traders")
    user_id = uuid.uuid4()
    make_merchant_member(fake_client, uuid.UUID(merchant["id"]), user_id, "MERCHANT_STAFF")
    fake_client.seed_auth_user(user_id, email="staff@example.com", full_name="Staff Person")

    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)
    response = client.get("/v1/admin/merchant-users", headers=auth_headers(admin_id))
    assert response.status_code == 200
    row = response.json()["data"][0]
    assert row["merchant_name"] == "Amani Traders"
    assert row["full_name"] == "Staff Person"
    assert row["email"] == "staff@example.com"
    assert row["role"] == "MERCHANT_STAFF"
    assert row["status"] == "active"
