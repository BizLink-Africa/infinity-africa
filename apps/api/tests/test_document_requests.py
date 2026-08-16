"""Merchant document requests: admin creates one from a fraud alert, merchant
submits evidence, admin approves — end to end against the FakeSupabaseClient.
"""

import io
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


def _merchant_and_admin(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    user_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, user_id, "MERCHANT_ADMIN")
    return merchant_id, user_id


def _pdf_file(name: str = "receipt.pdf"):
    return (name, io.BytesIO(b"%PDF-1.4\n%fake\n"), "application/pdf")


def test_admin_request_documents_notifies_merchant_and_flags_alert(fake_client):
    merchant_id, user_id = _merchant_and_admin(fake_client)
    alert = fake_client.seed(
        "fraud_alerts",
        {
            "merchant_id": str(merchant_id),
            "rule_code": "HIGH_VALUE_TRANSACTION",
            "risk_level": "MEDIUM",
            "reason": "Transaction requires review.",
            "status": "OPEN",
            "metadata": {},
        },
    )
    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)

    response = client.post(
        f"/v1/admin/risk-alerts/{alert['id']}/request-documents",
        headers=auth_headers(admin_id),
        json={"requested_documents": ["receipt", "proof_of_delivery"], "reason": "Please confirm delivery."},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "PENDING"

    updated_alert = next(r for r in fake_client.table("fraud_alerts")._table.rows if r["id"] == alert["id"])
    assert updated_alert["status"] == "DOCUMENTS_REQUESTED"

    notif = [
        n for n in fake_client.table("notifications")._table.rows
        if n["merchant_id"] == str(merchant_id) and n["notification_type"] == "document_request"
    ]
    assert len(notif) == 1
    assert notif[0]["title"] == "Supporting documents required for this transaction."

    # Merchant can see it in their own list
    list_response = client.get("/v1/merchant/document-requests", headers=auth_headers(user_id))
    assert list_response.status_code == 200
    assert len(list_response.json()["data"]) == 1


def test_merchant_submit_marks_request_submitted(fake_client):
    merchant_id, user_id = _merchant_and_admin(fake_client)
    request = fake_client.seed(
        "merchant_document_requests",
        {
            "merchant_id": str(merchant_id),
            "requested_documents": ["receipt"],
            "reason": "Please confirm.",
            "status": "PENDING",
        },
    )

    response = client.post(
        f"/v1/merchant/document-requests/{request['id']}/submit",
        headers=auth_headers(user_id),
        data={"document_label": "receipt"},
        files={"file": _pdf_file()},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "SUBMITTED"

    files = [f for f in fake_client.table("document_request_files")._table.rows if f["request_id"] == request["id"]]
    assert len(files) == 1
    assert files[0]["mime_type"] == "application/pdf"


def test_admin_approve_document_request(fake_client):
    merchant_id, _user_id = _merchant_and_admin(fake_client)
    request = fake_client.seed(
        "merchant_document_requests",
        {
            "merchant_id": str(merchant_id),
            "requested_documents": ["receipt"],
            "reason": "Please confirm.",
            "status": "SUBMITTED",
        },
    )
    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)

    response = client.patch(
        f"/v1/admin/document-requests/{request['id']}/approve", headers=auth_headers(admin_id)
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "APPROVED"
