"""Public dispute reporting, merchant response, and the refund workflow it
leads to — end to end against the FakeSupabaseClient.
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
    create_transaction,
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


def test_customer_can_submit_dispute_report_without_matching_a_transaction(fake_client):
    response = client.post(
        "/v1/public/disputes/report",
        data={
            "customer_name": "Amina Hassan",
            "customer_phone": "+255700111222",
            "reason_category": "PRODUCT_NOT_RECEIVED",
            "description": "Paid but never received the item.",
            "transaction_reference": "TXN-DOES-NOT-EXIST",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["status"] == "SUBMITTED"
    assert body["merchant_id"] is None


def test_customer_dispute_report_matches_real_transaction_and_notifies_merchant(fake_client):
    merchant_id, _user_id = _merchant_and_admin(fake_client)
    txn = create_transaction(fake_client, merchant_id, reference="TXN-MATCHME")

    response = client.post(
        "/v1/public/disputes/report",
        data={
            "customer_name": "Juma Athumani",
            "customer_phone": "+255700333444",
            "reason_category": "UNAUTHORIZED_PAYMENT",
            "description": "I did not authorize this payment.",
            "transaction_reference": "TXN-MATCHME",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["merchant_id"] == str(merchant_id)
    assert body["transaction_id"] == txn["id"]
    assert body["status"] == "MERCHANT_NOTIFIED"

    notifications = [
        n for n in fake_client.table("notifications")._table.rows
        if n["merchant_id"] == str(merchant_id) and n["notification_type"] == "dispute_received"
    ]
    assert len(notifications) == 1


def test_dispute_report_rejects_invalid_phone(fake_client):
    response = client.post(
        "/v1/public/disputes/report",
        data={
            "customer_name": "No Phone",
            "customer_phone": "abc",
            "reason_category": "OTHER",
            "description": "Test",
        },
    )
    assert response.status_code == 422


def test_merchant_can_respond_to_dispute(fake_client):
    merchant_id, user_id = _merchant_and_admin(fake_client)
    dispute = fake_client.seed(
        "disputes",
        {
            "merchant_id": str(merchant_id),
            "customer_name": "Test Customer",
            "customer_phone": "+255700555666",
            "reason_category": "OTHER",
            "description": "Issue description",
            "status": "MERCHANT_NOTIFIED",
            "evidence_files": [],
        },
    )

    response = client.post(
        f"/v1/merchant/disputes/{dispute['id']}/respond",
        headers=auth_headers(user_id),
        json={"body": "We shipped the item on the same day."},
    )
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["status"] == "UNDER_REVIEW"
    assert len(body["messages"]) == 1
    assert body["messages"][0]["sender_type"] == "merchant"


def test_merchant_cannot_respond_to_another_merchants_dispute(fake_client):
    other_merchant_id, _ = _merchant_and_admin(fake_client)
    dispute = fake_client.seed(
        "disputes",
        {
            "merchant_id": str(other_merchant_id),
            "customer_name": "Test Customer",
            "customer_phone": "+255700555666",
            "reason_category": "OTHER",
            "description": "Issue description",
            "status": "MERCHANT_NOTIFIED",
            "evidence_files": [],
        },
    )
    _my_merchant_id, my_user_id = _merchant_and_admin(fake_client)

    response = client.post(
        f"/v1/merchant/disputes/{dispute['id']}/respond",
        headers=auth_headers(my_user_id),
        json={"body": "Not my dispute"},
    )
    assert response.status_code == 404


def test_admin_can_request_refund(fake_client):
    merchant_id, _user_id = _merchant_and_admin(fake_client)
    txn = create_transaction(fake_client, merchant_id)
    dispute = fake_client.seed(
        "disputes",
        {
            "merchant_id": str(merchant_id),
            "transaction_id": txn["id"],
            "customer_name": "Test Customer",
            "customer_phone": "+255700777888",
            "reason_category": "REFUND_REQUESTED",
            "description": "Wants a refund",
            "status": "UNDER_REVIEW",
            "evidence_files": [],
        },
    )
    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)

    response = client.post(
        f"/v1/admin/disputes/{dispute['id']}/request-refund",
        headers=auth_headers(admin_id),
        json={"amount": "1000.00"},
    )
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["status"] == "REQUESTED"
    assert body["requested_by"] == "admin"
    assert body["transaction_id"] == txn["id"]

    updated_dispute = next(r for r in fake_client.table("disputes")._table.rows if r["id"] == dispute["id"])
    assert updated_dispute["status"] == "REFUND_REQUESTED"


def test_refund_reaching_success_posts_ledger_entry_and_notifies_merchant(fake_client):
    merchant_id, _user_id = _merchant_and_admin(fake_client)
    fake_client.seed(
        "ledger_accounts",
        {
            "merchant_id": str(merchant_id),
            "name": "Merchant Wallet (test)",
            "account_type": "liability",
            "purpose": "merchant_wallet",
            "currency": "TZS",
            "balance": "50000",
        },
    )
    txn = create_transaction(fake_client, merchant_id)
    dispute = fake_client.seed(
        "disputes",
        {
            "merchant_id": str(merchant_id),
            "transaction_id": txn["id"],
            "customer_name": "Test Customer",
            "customer_phone": "+255700999000",
            "reason_category": "REFUND_REQUESTED",
            "description": "Wants a refund",
            "status": "REFUND_REQUESTED",
            "evidence_files": [],
        },
    )
    fake_client.seed(
        "refunds",
        {
            "dispute_id": dispute["id"],
            "transaction_id": txn["id"],
            "merchant_id": str(merchant_id),
            "amount": "1000.00",
            "currency": "TZS",
            "status": "PROCESSING",
            "requested_by": "admin",
            "evidence_files": [],
        },
    )
    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)

    response = client.patch(
        f"/v1/admin/disputes/{dispute['id']}/refund-status",
        headers=auth_headers(admin_id),
        json={"status": "SUCCESS"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "SUCCESS"

    refund_txns = [
        t for t in fake_client.table("transactions")._table.rows
        if t["type"] == "refund" and t["merchant_id"] == str(merchant_id)
    ]
    assert len(refund_txns) == 1

    ledger_entries = [
        e for e in fake_client.table("ledger_entries")._table.rows if e["transaction_id"] == refund_txns[0]["id"]
    ]
    assert len(ledger_entries) == 2

    updated_dispute = next(r for r in fake_client.table("disputes")._table.rows if r["id"] == dispute["id"])
    assert updated_dispute["status"] == "REFUNDED"

    notifications = [
        n for n in fake_client.table("notifications")._table.rows
        if n["merchant_id"] == str(merchant_id) and "Refund completed" in n["title"]
    ]
    assert len(notifications) == 1
