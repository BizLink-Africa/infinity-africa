"""Merchant ID (merchants.merchant_code) — generation, format, uniqueness,
immutability, and exposure across signup/onboarding and Super Admin views.
See supabase/migrations/20260829010000_merchants_merchant_code.sql and
app/services/merchant_code.py.
"""

import re
import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.core.errors import MerchantCodeGenerationError
from app.main import app
from app.services.merchant_code import generate_merchant_code
from tests.factories import (
    TEST_JWT_SECRET,
    auth_headers,
    create_merchant,
    make_super_admin,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _admin_headers(fake_client) -> dict:
    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)
    return auth_headers(admin_id)


# --- app/services/merchant_code.py — the generator itself -------------------


def test_generate_merchant_code_is_exactly_8_digits_starting_with_27(fake_client):
    code = generate_merchant_code(fake_client)
    assert re.fullmatch(r"27\d{6}", code)


def test_generate_merchant_code_does_not_collide_with_an_existing_merchant(fake_client, monkeypatch):
    """Forces the first candidate to collide with an already-taken code,
    then asserts the generator retries rather than returning the taken
    value — the DB-uniqueness-check-then-retry loop the task requires."""
    taken = "27111111"
    create_merchant(fake_client, merchant_code=taken)

    candidates = iter([111111, 222222])
    monkeypatch.setattr("app.services.merchant_code.secrets.randbelow", lambda _n: next(candidates))

    code = generate_merchant_code(fake_client)
    assert code == "27222222"


def test_generate_merchant_code_fails_safely_after_exhausting_retries(fake_client, monkeypatch):
    """Every candidate collides — must raise a clear, typed error rather
    than looping forever or silently reusing a taken code."""
    create_merchant(fake_client, merchant_code="27333333")
    monkeypatch.setattr("app.services.merchant_code.secrets.randbelow", lambda _n: 333333)

    with pytest.raises(MerchantCodeGenerationError):
        generate_merchant_code(fake_client)


def test_generate_merchant_code_is_unique_across_many_calls(fake_client):
    codes = set()
    for _ in range(25):
        code = generate_merchant_code(fake_client)
        assert code not in codes
        codes.add(code)
        create_merchant(fake_client, merchant_code=code)
    assert len(codes) == 25


# --- Super admin manual merchant creation (POST /v1/merchants) --------------


def _valid_merchant_payload(**overrides) -> dict:
    return {
        "business_name": "Masanja Traders",
        "contact_email": "masanja@example.com",
        **overrides,
    }


def test_admin_created_merchant_gets_a_merchant_code(fake_client):
    response = client.post(
        "/v1/merchants", headers=_admin_headers(fake_client), json=_valid_merchant_payload()
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert re.fullmatch(r"27\d{6}", body["merchant_code"])


def test_two_admin_created_merchants_get_different_merchant_codes(fake_client):
    headers = _admin_headers(fake_client)
    first = client.post("/v1/merchants", headers=headers, json=_valid_merchant_payload()).json()["data"]
    second = client.post(
        "/v1/merchants", headers=headers, json=_valid_merchant_payload(contact_email="other@example.com")
    ).json()["data"]
    assert first["merchant_code"] != second["merchant_code"]


def test_merchant_code_is_not_an_updatable_profile_field(fake_client):
    """MerchantProfileUpdate (PATCH /v1/merchants/{id}, merchant-editable)
    must not accept merchant_code at all — immutability enforced by the
    schema simply never exposing it as a writable field, not by runtime
    guard logic that could be bypassed."""
    from app.schemas.merchants import MerchantProfileUpdate

    assert "merchant_code" not in MerchantProfileUpdate.model_fields


# --- merchant_code is identification, not a secret ---------------------------


def test_merchant_code_appears_in_plain_super_admin_merchant_list_response(fake_client):
    merchant = create_merchant(fake_client, business_name="Kilimanjaro Cafe")
    response = client.get("/v1/admin/merchants", headers=_admin_headers(fake_client))
    assert response.status_code == 200
    row = next(r for r in response.json()["data"] if r["merchant_id"] == merchant["id"])
    # No masking/redaction — merchant_code is safe to show in full, unlike
    # an API key (see ApiKeyResponse, which never returns the raw secret).
    assert row["merchant_code"] == merchant["merchant_code"]
