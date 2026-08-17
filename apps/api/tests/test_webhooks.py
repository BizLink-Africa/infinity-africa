"""POST /v1/webhooks/selcom: raw body + signature verification, storage in
selcom_webhook_events, duplicate-delivery prevention, and successful
collection processing (status update, ledger posting, merchant balance
update, payment_link.paid) — end to end against the in-memory
FakeSupabaseClient (see tests/fakes.py).
"""

import json
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services.selcom.client import get_selcom_client
from app.services.selcom.webhooks import compute_selcom_signature
from app.services.selcom_business.client import get_selcom_business_client
from tests.factories import (
    TEST_JWT_SECRET,
    auth_headers,
    create_merchant,
    make_merchant_member,
    make_super_admin,
)

client = TestClient(app)

_SELCOM_WEBHOOK_SECRET = "test-selcom-webhook-secret"


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("SELCOM_BUSINESS_MODE", "mock")
    monkeypatch.setenv("MOCK_PROVIDER_FAILURE_RATE", "0")
    monkeypatch.setenv("MOCK_PROVIDER_LATENCY_SECONDS", "0")
    monkeypatch.setenv("SELCOM_WEBHOOK_SECRET", _SELCOM_WEBHOOK_SECRET)
    get_settings.cache_clear()
    get_selcom_client.cache_clear()
    get_selcom_business_client.cache_clear()
    yield
    get_settings.cache_clear()
    get_selcom_client.cache_clear()
    get_selcom_business_client.cache_clear()


def _merchant_and_admin(fake_client, **overrides):
    merchant = create_merchant(fake_client, **overrides)
    merchant_id = uuid.UUID(merchant["id"])
    admin_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, admin_id, "MERCHANT_ADMIN")
    return merchant_id, admin_id


def _initiate_collection(merchant_id: uuid.UUID, admin_id: uuid.UUID, **body_overrides) -> dict:
    body = {
        "merchant_id": str(merchant_id),
        "amount": "1000.00",
        "customer_phone": "+255700000000",
        **body_overrides,
    }
    response = client.post(
        "/v1/collections/stk-push",
        headers={**auth_headers(admin_id), "Idempotency-Key": str(uuid.uuid4())},
        json=body,
    )
    assert response.status_code == 202, response.text
    return response.json()["data"]


def _fund_wallet(fake_client, merchant_id: uuid.UUID, amount: str, currency: str = "TZS") -> None:
    fake_client.seed(
        "ledger_accounts",
        {
            "merchant_id": str(merchant_id),
            "name": "Merchant Wallet (test)",
            "account_type": "liability",
            "purpose": "merchant_wallet",
            "currency": currency,
            "balance": amount,
        },
    )


def _wallet_balance(fake_client, merchant_id: uuid.UUID) -> Decimal:
    account = next(
        a
        for a in fake_client.table("ledger_accounts")._table.rows
        if a["purpose"] == "merchant_wallet" and a["merchant_id"] == str(merchant_id)
    )
    return Decimal(str(account["balance"]))


def _request_disbursement(fake_client, merchant_id: uuid.UUID, admin_id: uuid.UUID, amount: str, **overrides) -> dict:
    """Creates a withdrawal and immediately approves it (as a freshly
    seeded Super Admin) — every withdrawal now starts PENDING_ADMIN_APPROVAL
    and only reaches Selcom once approved, so callers exercising the
    provider/webhook-callback machinery need it approved first."""
    body = {
        "merchant_id": str(merchant_id),
        "amount": amount,
        "destination_name": "Jane Doe",
        "destination_identifier": "+255700000000",
        "destination_code": "MPESA",
        **overrides,
    }
    response = client.post(
        "/v1/disbursements/mobile-money",
        headers={**auth_headers(admin_id), "Idempotency-Key": str(uuid.uuid4())},
        json=body,
    )
    assert response.status_code == 202, response.text
    created = response.json()["data"]

    super_admin_id = uuid.uuid4()
    make_super_admin(fake_client, super_admin_id)
    approved = client.post(
        f"/v1/admin/withdrawals/{created['id']}/approve", headers=auth_headers(super_admin_id)
    )
    assert approved.status_code == 200, approved.text
    return approved.json()["data"]


def _post_selcom_webhook(*, event_id: str, event_type: str, provider_reference: str, failure_reason=None):
    body = {
        "event_id": event_id,
        "event_type": event_type,
        "provider_reference": provider_reference,
        "failure_reason": failure_reason,
    }
    raw_body = json.dumps(body).encode("utf-8")
    signature = compute_selcom_signature(raw_body=raw_body, secret=_SELCOM_WEBHOOK_SECRET)
    return client.post(
        "/v1/webhooks/selcom",
        content=raw_body,
        headers={"Content-Type": "application/json", "X-Selcom-Signature": signature},
    )


# --- signature verification --------------------------------------------------


def test_invalid_signature_is_rejected(fake_client):
    merchant_id, admin_id = _merchant_and_admin(fake_client, webhook_url="https://merchant.example.com/hooks")
    initiate = _initiate_collection(merchant_id, admin_id)

    body = {
        "event_id": str(uuid.uuid4()),
        "event_type": "collection.success",
        "provider_reference": initiate["provider_reference"],
        "failure_reason": None,
    }
    response = client.post(
        "/v1/webhooks/selcom",
        content=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Selcom-Signature": "not-the-right-signature"},
    )

    assert response.status_code == 401

    collection_row = next(
        r for r in fake_client.table("collections")._table.rows if r["id"] == initiate["id"]
    )
    assert collection_row["status"] == "processing"

    stored = fake_client.table("selcom_webhook_events")._table.rows
    assert len(stored) == 1
    assert stored[0]["status"] == "failed"
    assert stored[0]["signature_valid"] is False


# --- successful collection processing ---------------------------------------


def test_successful_collection_webhook_updates_status_ledger_and_balance(fake_client):
    merchant_id, admin_id = _merchant_and_admin(fake_client, webhook_url="https://merchant.example.com/hooks")
    initiate = _initiate_collection(merchant_id, admin_id)

    response = _post_selcom_webhook(
        event_id=str(uuid.uuid4()),
        event_type="collection.success",
        provider_reference=initiate["provider_reference"],
    )

    assert response.status_code == 200
    assert response.json()["data"]["resolved"] == "collection"

    collection_row = next(
        r for r in fake_client.table("collections")._table.rows if r["id"] == initiate["id"]
    )
    assert collection_row["status"] == "successful"

    transaction = next(
        t for t in fake_client.table("transactions")._table.rows if t["collection_id"] == initiate["id"]
    )
    assert transaction["status"] == "successful"

    entries = [
        e for e in fake_client.table("ledger_entries")._table.rows if e["transaction_id"] == transaction["id"]
    ]
    debits = sum(Decimal(e["amount"]) for e in entries if e["direction"] == "debit")
    credits = sum(Decimal(e["amount"]) for e in entries if e["direction"] == "credit")
    assert debits == credits > 0

    wallet_account = next(
        a
        for a in fake_client.table("ledger_accounts")._table.rows
        if a["purpose"] == "merchant_wallet" and a["merchant_id"] == str(merchant_id)
    )
    assert Decimal(wallet_account["balance"]) == Decimal(str(transaction["net_amount"]))

    settlement_account = next(
        a for a in fake_client.table("ledger_accounts")._table.rows if a["purpose"] == "settlement_clearing"
    )
    assert Decimal(settlement_account["balance"]) == Decimal(str(transaction["gross_amount"]))

    events = fake_client.table("webhook_events")._table.rows
    assert any(e["event_name"] == "collection.success" for e in events)

    stored = fake_client.table("selcom_webhook_events")._table.rows
    assert len(stored) == 1
    assert stored[0]["status"] == "processed"
    assert stored[0]["signature_valid"] is True


def test_successful_collection_webhook_marks_linked_payment_link_paid(fake_client):
    merchant_id, admin_id = _merchant_and_admin(fake_client, webhook_url="https://merchant.example.com/hooks")

    link_response = client.post(
        "/v1/payment-links",
        headers={**auth_headers(admin_id), "Idempotency-Key": str(uuid.uuid4())},
        json={
            "merchant_id": str(merchant_id),
            "amount": "1000.00",
            "currency": "TZS",
            "allowed_payment_methods": ["STK_PUSH"],
        },
    )
    assert link_response.status_code == 201, link_response.text
    link = link_response.json()["data"]

    initiate = _initiate_collection(merchant_id, admin_id, payment_link_id=link["id"])

    _post_selcom_webhook(
        event_id=str(uuid.uuid4()),
        event_type="collection.success",
        provider_reference=initiate["provider_reference"],
    )

    link_row = next(r for r in fake_client.table("payment_links")._table.rows if r["id"] == link["id"])
    assert link_row["status"] == "PAID"

    events = fake_client.table("webhook_events")._table.rows
    assert any(e["event_name"] == "payment_link.paid" for e in events)


def test_failed_collection_webhook_updates_status_without_ledger_entries(fake_client):
    merchant_id, admin_id = _merchant_and_admin(fake_client, webhook_url="https://merchant.example.com/hooks")
    initiate = _initiate_collection(merchant_id, admin_id)

    response = _post_selcom_webhook(
        event_id=str(uuid.uuid4()),
        event_type="collection.failed",
        provider_reference=initiate["provider_reference"],
        failure_reason="Customer cancelled the push",
    )

    assert response.status_code == 200
    assert response.json()["data"]["resolved"] == "collection"

    collection_row = next(
        r for r in fake_client.table("collections")._table.rows if r["id"] == initiate["id"]
    )
    assert collection_row["status"] == "failed"
    assert fake_client.table("ledger_entries")._table.rows == []

    events = fake_client.table("webhook_events")._table.rows
    assert any(e["event_name"] == "collection.failed" for e in events)


# --- duplicate webhook prevention --------------------------------------------


def test_duplicate_webhook_delivery_is_not_reprocessed(fake_client):
    merchant_id, admin_id = _merchant_and_admin(fake_client, webhook_url="https://merchant.example.com/hooks")
    initiate = _initiate_collection(merchant_id, admin_id)
    event_id = str(uuid.uuid4())

    first = _post_selcom_webhook(
        event_id=event_id, event_type="collection.success", provider_reference=initiate["provider_reference"]
    )
    assert first.status_code == 200
    assert first.json()["data"]["resolved"] == "collection"

    second = _post_selcom_webhook(
        event_id=event_id, event_type="collection.success", provider_reference=initiate["provider_reference"]
    )
    assert second.status_code == 200
    assert second.json()["data"]["status"] == "duplicate"

    # Only ever stored once, and downstream side effects only ran once.
    stored = fake_client.table("selcom_webhook_events")._table.rows
    assert len(stored) == 1

    transactions = [
        t for t in fake_client.table("transactions")._table.rows if t["collection_id"] == initiate["id"]
    ]
    assert len(transactions) == 1
    entries = [
        e for e in fake_client.table("ledger_entries")._table.rows if e["transaction_id"] == transactions[0]["id"]
    ]
    # One debit + one credit (no fee at 0% platform_fee_percentage default... actually
    # platform_fee_percentage defaults to 1.5, so 3 entries: settlement debit,
    # wallet credit, revenue credit) — the assertion that matters is that this
    # set wasn't duplicated by the second delivery.
    assert len(entries) in (2, 3)

    collection_row = next(
        r for r in fake_client.table("collections")._table.rows if r["id"] == initiate["id"]
    )
    assert collection_row["status"] == "successful"


# --- withdrawal (disbursement) reversal --------------------------------------


def test_withdrawal_reversed_webhook_reverses_successful_payout(fake_client):
    """A withdrawal.reversed callback (Selcom's alias — routes the same as
    disbursement.reversed) reverses an already-SUCCESS payout: credits the
    wallet back, marks the disbursement REVERSED, notifies the merchant,
    and is safe to retry without double-crediting."""
    merchant_id, admin_id = _merchant_and_admin(fake_client, webhook_url="https://merchant.example.com/hooks")
    _fund_wallet(fake_client, merchant_id, "10000.00")
    disbursement = _request_disbursement(fake_client, merchant_id, admin_id, "4000.00")
    assert disbursement["status"] == "SUCCESS"
    assert _wallet_balance(fake_client, merchant_id) == Decimal("6000.00")

    response = _post_selcom_webhook(
        event_id=str(uuid.uuid4()),
        event_type="withdrawal.reversed",
        provider_reference=disbursement["provider_reference"],
        failure_reason="Bank rejected the account after settlement",
    )

    assert response.status_code == 200
    assert response.json()["data"]["resolved"] == "disbursement_reversal"

    disbursement_row = next(
        r for r in fake_client.table("disbursements")._table.rows if r["id"] == disbursement["id"]
    )
    assert disbursement_row["status"] == "REVERSED"
    assert _wallet_balance(fake_client, merchant_id) == Decimal("10000.00")

    notifications = fake_client.table("notifications")._table.rows
    assert any(n["notification_type"] == "withdrawal_reversed" for n in notifications)

    audit_events = [a for a in fake_client.table("audit_logs")._table.rows if a["action"] == "disbursement.reversed"]
    assert len(audit_events) == 1

    events = fake_client.table("webhook_events")._table.rows
    assert any(e["event_name"] == "disbursement.reversed" for e in events)

    # A retried delivery (different event_id, same provider_reference) finds
    # the disbursement already REVERSED and no-ops rather than double-crediting.
    retry = _post_selcom_webhook(
        event_id=str(uuid.uuid4()),
        event_type="withdrawal.reversed",
        provider_reference=disbursement["provider_reference"],
    )
    assert retry.json()["data"]["resolved"] == "none"
    assert _wallet_balance(fake_client, merchant_id) == Decimal("10000.00")
