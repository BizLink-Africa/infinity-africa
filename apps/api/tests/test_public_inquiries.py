"""POST /v1/public/inquiries — apps/web's marketing-site contact form.
Saves the inquiry first, notifies the CEO best-effort second — an email
failure must never lose the inquiry itself.
"""

import pytest
import resend
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from tests.factories import TEST_JWT_SECRET

client = TestClient(app)

_VALID_PAYLOAD = {
    "full_name": "Amani Mushi",
    "business_name": "Amani Traders Ltd",
    "email": "amani@example.com",
    "phone": "+255700000000",
    "message": "I'd like to accept mobile money payments for my shop.",
}


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("RESEND_API_KEY", "test-resend-key-do-not-use-in-production")
    monkeypatch.setenv("CEO_EMAIL", "ceo@infinityafrica.net")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class _FakeResend:
    def __init__(self):
        self.calls: list[dict] = []
        self.should_fail = False

    def send(self, params: dict) -> dict:
        self.calls.append(params)
        if self.should_fail:
            raise Exception("Resend rejected the request")  # noqa: TRY002
        return {"id": "resend-test-message-id"}


@pytest.fixture(autouse=True)
def fake_resend(monkeypatch):
    fake = _FakeResend()
    monkeypatch.setattr(resend.Emails, "send", fake.send)
    return fake


def test_inquiry_is_saved(fake_client):
    response = client.post("/v1/public/inquiries", json=_VALID_PAYLOAD)

    assert response.status_code == 200, response.text
    rows = fake_client.table("inquiries")._table.rows
    assert len(rows) == 1
    assert rows[0]["full_name"] == "Amani Mushi"
    assert rows[0]["email"] == "amani@example.com"
    assert rows[0]["source"] == "contact_page"


def test_inquiry_notifies_the_ceo(fake_client, fake_resend):
    response = client.post("/v1/public/inquiries", json=_VALID_PAYLOAD)

    assert response.status_code == 200
    assert len(fake_resend.calls) == 1
    assert fake_resend.calls[0]["to"] == ["ceo@infinityafrica.net"]
    assert fake_resend.calls[0]["subject"] == "New Infinity Africa inquiry received"
    assert "Amani Mushi" in fake_resend.calls[0]["html"]
    assert "Amani Traders Ltd" in fake_resend.calls[0]["html"]
    assert "amani@example.com" in fake_resend.calls[0]["html"]


def test_inquiry_is_kept_even_when_the_notification_email_fails(fake_client, fake_resend):
    fake_resend.should_fail = True

    response = client.post("/v1/public/inquiries", json=_VALID_PAYLOAD)

    assert response.status_code == 200, response.text
    assert len(fake_client.table("inquiries")._table.rows) == 1


def test_inquiry_requires_a_message_and_email(fake_client):
    response = client.post("/v1/public/inquiries", json={"full_name": "No Message", "email": "x@example.com", "message": ""})
    assert response.status_code == 422

    response = client.post("/v1/public/inquiries", json={"full_name": "Bad Email", "email": "not-an-email", "message": "hi"})
    assert response.status_code == 422
