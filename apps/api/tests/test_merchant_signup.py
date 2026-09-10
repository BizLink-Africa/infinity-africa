"""Combined merchant signup — POST /v1/onboarding/signup — account
credentials + business details + mandatory NIDA in one unauthenticated
call. The backend creates the Supabase Auth user itself (service_role);
the merchant is created PENDING_VERIFICATION and is never auto-approved.
CEO gets a signup notification; the merchant approval/welcome email is
NOT sent here (only on Super Admin approval).
"""

import logging
import uuid

import pytest
import resend
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

client = TestClient(app)

_NIDA = "19900101-12345-12345-12"
_NIDA_DIGITS = "19900101123451234512"


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret-do-not-use")
    monkeypatch.setenv("RESEND_API_KEY", "test-resend-key-do-not-use-in-production")
    monkeypatch.setenv("CEO_EMAIL", "ceo@infinityafrica.net")
    monkeypatch.setenv("APP_URL", "https://infinityafrica.net")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class _FakeResend:
    def __init__(self):
        self.calls: list[dict] = []

    def send(self, params: dict) -> dict:
        self.calls.append(params)
        return {"id": "resend-test-message-id"}


@pytest.fixture(autouse=True)
def fake_resend(monkeypatch):
    fake = _FakeResend()
    monkeypatch.setattr(resend.Emails, "send", fake.send)
    return fake


def _payload(**overrides) -> dict:
    return {
        "full_name": "Amani Mushi",
        "email": f"amani-{uuid.uuid4().hex[:8]}@example.com",
        "phone": "+255700000000",
        "contact_phone": "+255700000000",
        "password": "Str0ng!pass",
        "nida_number": _NIDA,
        "business_name": "Amani Traders Ltd",
        "nature_of_business": "Online retail",
        "business_category": "Retail",
        "physical_address": "Mbezi",
        "region_city": "Dar es Salaam",
        "website_url": None,
        "services_needed": ["PAYMENT_LINKS"],
        "accepted_terms": True,
        "accepted_privacy": True,
        **overrides,
    }


def test_signup_creates_user_merchant_and_pending_submission(fake_client):
    body = _payload()
    response = client.post("/v1/onboarding/signup", json=body)
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["account_status"] == "PENDING_VERIFICATION"
    assert data["email_confirmation_required"] is True

    # Supabase auth user created (service_role, backend-side)
    assert any(u.email == body["email"] for u in fake_client.auth.admin._users.values())

    # merchant + membership + submission all created, merchant PENDING
    merchant = next(m for m in fake_client.table("merchants")._table.rows if m["id"] == str(data["merchant_id"]))
    assert merchant["status"] == "pending"
    assert merchant["kyc_status"] == "unverified"
    assert merchant["contact_email"] == body["email"]
    membership = next(
        mu for mu in fake_client.table("merchant_users")._table.rows if mu["merchant_id"] == str(data["merchant_id"])
    )
    assert membership["role"] == "MERCHANT_ADMIN"
    submission = next(
        s for s in fake_client.table("onboarding_submissions")._table.rows if s["merchant_id"] == str(data["merchant_id"])
    )
    assert submission["review_status"] == "PENDING_VERIFICATION"
    assert submission["nida_number"] == _NIDA_DIGITS  # stored digits-only


def test_signup_requires_nida(fake_client):
    response = client.post("/v1/onboarding/signup", json=_payload(nida_number=""))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "nida_required"
    assert fake_client.table("merchants")._table.rows == []


def test_signup_rejects_malformed_nida(fake_client):
    response = client.post("/v1/onboarding/signup", json=_payload(nida_number="12345"))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "nida_invalid"
    assert fake_client.table("merchants")._table.rows == []


def test_signup_duplicate_email_conflicts(fake_client):
    body = _payload()
    assert client.post("/v1/onboarding/signup", json=body).status_code == 201
    second = client.post("/v1/onboarding/signup", json={**_payload(), "email": body["email"]})
    assert second.status_code == 409
    # only one merchant created
    assert len(fake_client.table("merchants")._table.rows) == 1


def test_signup_notifies_ceo_with_masked_nida_not_full(fake_client, fake_resend):
    client.post("/v1/onboarding/signup", json=_payload())

    ceo_calls = [c for c in fake_resend.calls if c["to"] == ["ceo@infinityafrica.net"]]
    assert len(ceo_calls) == 1
    ceo = ceo_calls[0]
    assert ceo["subject"] == "New merchant signup submitted"
    assert ceo["from"] == "Infinity Africa <notification@infinityafrica.net>"
    assert ceo["reply_to"] == "info@infinityafrica.net"
    # masked NIDA present, full NIDA absent
    assert "4512" in ceo["html"]
    assert _NIDA_DIGITS not in ceo["html"]
    assert _NIDA not in ceo["html"]
    assert "collected offline" in ceo["html"].lower()


def test_signup_does_not_send_approval_email(fake_client, fake_resend):
    client.post("/v1/onboarding/signup", json=_payload())
    approval_calls = [c for c in fake_resend.calls if c["subject"] == "Your Infinity Africa account has been approved"]
    assert approval_calls == []
    # the email-verification email IS sent, to the merchant, not the CEO
    verify_calls = [c for c in fake_resend.calls if c["subject"] == "Confirm your email address"]
    assert len(verify_calls) == 1
    assert verify_calls[0]["to"] != ["ceo@infinityafrica.net"]


def test_signup_does_not_log_full_nida(fake_client, caplog):
    with caplog.at_level(logging.DEBUG):
        client.post("/v1/onboarding/signup", json=_payload())
    assert _NIDA_DIGITS not in caplog.text
    assert _NIDA not in caplog.text


def test_signup_is_rate_limited(fake_client):
    from app.core.rate_limit import _limiter

    for _ in range(5):
        _limiter.check("merchant_signup:testclient", limit=5, window_seconds=300)

    response = client.post("/v1/onboarding/signup", json=_payload())
    assert response.status_code == 429
