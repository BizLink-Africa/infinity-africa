"""Self-service merchant team management — /v1/merchant/users*
(app/routers/merchant_portal.py's "Team / Users" section). Same
FakeSupabaseClient pattern as test_merchant_portal.py.
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
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _admin(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    admin_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, admin_id, "MERCHANT_ADMIN")
    fake_client.seed_auth_user(admin_id, email="admin@example.com", full_name="Amina Admin")
    return merchant_id, admin_id


# --- GET /users/me ------------------------------------------------------------


def test_get_my_membership_returns_own_profile(fake_client):
    _merchant_id, admin_id = _admin(fake_client)
    response = client.get("/v1/merchant/users/me", headers=auth_headers(admin_id))
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["full_name"] == "Amina Admin"
    assert body["email"] == "admin@example.com"
    assert body["role"] == "MERCHANT_ADMIN"


def test_get_my_membership_works_for_staff_too(fake_client):
    merchant_id, _admin_id = _admin(fake_client)
    staff_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, staff_id, "MERCHANT_STAFF")
    fake_client.seed_auth_user(staff_id, email="staff@example.com", full_name="Sam Staff")
    response = client.get("/v1/merchant/users/me", headers=auth_headers(staff_id))
    assert response.status_code == 200
    assert response.json()["data"]["role"] == "MERCHANT_STAFF"


# --- POST /users (create/invite) ----------------------------------------------


def test_admin_can_invite_a_new_merchant_user(fake_client):
    _merchant_id, admin_id = _admin(fake_client)
    response = client.post(
        "/v1/merchant/users",
        headers=auth_headers(admin_id),
        json={"full_name": "David Komba", "email": "david@example.com", "role": "MERCHANT_STAFF"},
    )
    assert response.status_code == 201, response.text
    body = response.json()["data"]
    assert body["full_name"] == "David Komba"
    assert body["email"] == "david@example.com"
    assert body["role"] == "MERCHANT_STAFF"
    assert body["status"] == "invited"

    listing = client.get("/v1/merchant/users", headers=auth_headers(admin_id))
    names = [row["full_name"] for row in listing.json()["data"]]
    assert "David Komba" in names


def test_staff_cannot_invite_a_new_merchant_user(fake_client):
    merchant_id, _admin_id = _admin(fake_client)
    staff_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, staff_id, "MERCHANT_STAFF")
    response = client.post(
        "/v1/merchant/users",
        headers=auth_headers(staff_id),
        json={"full_name": "David Komba", "email": "david@example.com", "role": "MERCHANT_STAFF"},
    )
    assert response.status_code == 403


def test_invite_requires_a_full_name(fake_client):
    _merchant_id, admin_id = _admin(fake_client)
    response = client.post(
        "/v1/merchant/users",
        headers=auth_headers(admin_id),
        json={"full_name": "  ", "email": "david@example.com", "role": "MERCHANT_STAFF"},
    )
    assert response.status_code == 422


def test_invite_rejects_super_admin_role(fake_client):
    _merchant_id, admin_id = _admin(fake_client)
    response = client.post(
        "/v1/merchant/users",
        headers=auth_headers(admin_id),
        json={"full_name": "David Komba", "email": "david@example.com", "role": "SUPER_ADMIN"},
    )
    assert response.status_code == 422


def test_invite_rejects_already_registered_email(fake_client):
    _merchant_id, admin_id = _admin(fake_client)
    response = client.post(
        "/v1/merchant/users",
        headers=auth_headers(admin_id),
        json={"full_name": "Amina Duplicate", "email": "admin@example.com", "role": "MERCHANT_STAFF"},
    )
    assert response.status_code == 409


# --- PATCH /users/{id} ---------------------------------------------------------


def test_admin_can_update_a_teammates_role(fake_client):
    merchant_id, admin_id = _admin(fake_client)
    staff_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, staff_id, "MERCHANT_STAFF")
    listing = client.get("/v1/merchant/users", headers=auth_headers(admin_id)).json()["data"]
    row_id = next(r["id"] for r in listing if r["user_id"] == str(staff_id))

    response = client.patch(
        f"/v1/merchant/users/{row_id}", headers=auth_headers(admin_id), json={"role": "DEVELOPER"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["role"] == "DEVELOPER"


def test_admin_cannot_change_their_own_role_via_this_endpoint(fake_client):
    _merchant_id, admin_id = _admin(fake_client)
    listing = client.get("/v1/merchant/users", headers=auth_headers(admin_id)).json()["data"]
    own_row_id = next(r["id"] for r in listing if r["user_id"] == str(admin_id))

    response = client.patch(
        f"/v1/merchant/users/{own_row_id}", headers=auth_headers(admin_id), json={"role": "MERCHANT_STAFF"}
    )
    assert response.status_code == 409


# --- POST /users/{id}/deactivate ----------------------------------------------


def test_admin_can_deactivate_a_teammate(fake_client):
    merchant_id, admin_id = _admin(fake_client)
    staff_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, staff_id, "MERCHANT_STAFF")
    listing = client.get("/v1/merchant/users", headers=auth_headers(admin_id)).json()["data"]
    row_id = next(r["id"] for r in listing if r["user_id"] == str(staff_id))

    response = client.post(f"/v1/merchant/users/{row_id}/deactivate", headers=auth_headers(admin_id))
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "suspended"


def test_admin_cannot_deactivate_themself(fake_client):
    _merchant_id, admin_id = _admin(fake_client)
    listing = client.get("/v1/merchant/users", headers=auth_headers(admin_id)).json()["data"]
    own_row_id = next(r["id"] for r in listing if r["user_id"] == str(admin_id))

    response = client.post(f"/v1/merchant/users/{own_row_id}/deactivate", headers=auth_headers(admin_id))
    assert response.status_code == 409
