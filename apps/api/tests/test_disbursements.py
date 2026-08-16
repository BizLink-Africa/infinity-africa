"""Disbursements module: balance validation, reservation/settlement,
idempotency, the high-value approval queue, and list/get scoping — end to
end against the in-memory FakeSupabaseClient (see tests/fakes.py).
"""

import uuid
from decimal import Decimal

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
    monkeypatch.setenv("DISBURSEMENT_APPROVAL_THRESHOLD", "1000000")
    get_settings.cache_clear()
    get_selcom_client.cache_clear()
    yield
    get_settings.cache_clear()
    get_selcom_client.cache_clear()


def _merchant_and_admin(fake_client, **merchant_overrides):
    merchant = create_merchant(fake_client, **merchant_overrides)
    merchant_id = uuid.UUID(merchant["id"])
    admin_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, admin_id, "MERCHANT_ADMIN")
    return merchant_id, admin_id


def _fund_wallet(fake_client, merchant_id: uuid.UUID, amount: str, currency: str = "TZS") -> None:
    """Seeds a merchant_wallet ledger_accounts row directly, so a
    disbursement test doesn't need to run a whole collection first just to
    have a balance to pay out from."""
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


def _request_mobile_money(merchant_id: uuid.UUID, admin_id: uuid.UUID, amount: str, **overrides):
    body = {
        "merchant_id": str(merchant_id),
        "amount": amount,
        "destination_name": "Jane Doe",
        "destination_identifier": "+255700000000",
        **overrides,
    }
    return client.post(
        "/v1/disbursements/mobile-money",
        headers={**auth_headers(admin_id), "Idempotency-Key": str(uuid.uuid4())},
        json=body,
    )


# --- merchant verification gate ----------------------------------------------


def test_unverified_merchant_cannot_withdraw(fake_client):
    """Withdrawals require a verified, active merchant account — enforced
    regardless of mock/live mode (mock mode mirrors live behavior, it isn't
    a verification-free sandbox)."""
    merchant_id, admin_id = _merchant_and_admin(fake_client, status="pending", kyc_status="unverified")
    _fund_wallet(fake_client, merchant_id, "10000.00")

    response = _request_mobile_money(merchant_id, admin_id, "1000.00")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "withdrawal_restricted"
    assert fake_client.table("disbursements")._table.rows == []
    assert _wallet_balance(fake_client, merchant_id) == Decimal("10000.00")


def test_suspended_merchant_cannot_withdraw_even_if_previously_verified(fake_client):
    merchant_id, admin_id = _merchant_and_admin(fake_client, status="suspended", kyc_status="verified")
    _fund_wallet(fake_client, merchant_id, "10000.00")

    response = _request_mobile_money(merchant_id, admin_id, "1000.00")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "withdrawal_restricted"


def test_approved_merchant_can_withdraw(fake_client):
    """create_merchant() defaults to status="active", kyc_status="verified"
    — the "APPROVED" state — so this is the baseline every other test in
    this file already relies on; asserted explicitly here."""
    merchant_id, admin_id = _merchant_and_admin(fake_client, status="active", kyc_status="verified")
    _fund_wallet(fake_client, merchant_id, "10000.00")

    response = _request_mobile_money(merchant_id, admin_id, "1000.00")

    assert response.status_code == 202, response.text
    assert response.json()["data"]["status"] == "SUCCESS"


# --- insufficient balance ----------------------------------------------------


def test_disbursement_rejected_for_insufficient_balance(fake_client):
    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "100.00")

    response = _request_mobile_money(merchant_id, admin_id, "5000.00")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_balance"
    assert fake_client.table("disbursements")._table.rows == []
    assert _wallet_balance(fake_client, merchant_id) == Decimal("100.00")


def test_disbursement_rejected_when_wallet_has_no_balance_at_all(fake_client):
    """A brand new merchant with no ledger_accounts row yet — get_wallet_balance
    treats that as zero rather than erroring."""
    merchant_id, admin_id = _merchant_and_admin(fake_client)

    response = _request_mobile_money(merchant_id, admin_id, "1.00")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_balance"


# --- successful request -------------------------------------------------


def test_successful_disbursement_request(fake_client):
    merchant_id, admin_id = _merchant_and_admin(fake_client, webhook_url="https://merchant.example.com/hooks")
    _fund_wallet(fake_client, merchant_id, "10000.00")

    response = _request_mobile_money(merchant_id, admin_id, "4000.00")

    assert response.status_code == 202, response.text
    body = response.json()["data"]
    assert body["status"] == "SUCCESS"
    assert body["requires_approval"] is False
    assert body["provider_reference"] is not None
    assert body["method"] == "MOBILE_MONEY"

    assert _wallet_balance(fake_client, merchant_id) == Decimal("6000.00")

    transaction = next(
        t for t in fake_client.table("transactions")._table.rows if t["disbursement_id"] == body["id"]
    )
    assert transaction["status"] == "successful"
    assert transaction["type"] == "disbursement"
    assert Decimal(transaction["gross_amount"]) == Decimal("4000.00")

    events = fake_client.table("webhook_events")._table.rows
    assert any(e["event_name"] == "disbursement.success" for e in events)

    # Response-only enrichment fields (not disbursements table columns).
    assert body["transaction_reference"] == transaction["reference"]
    assert Decimal(body["fee_amount"]) == Decimal(transaction["fee_amount"])
    assert Decimal(body["net_amount"]) == Decimal(transaction["net_amount"])


def test_selcom_pesa_disbursement_endpoint(fake_client):
    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "10000.00")

    response = client.post(
        "/v1/disbursements/selcom-pesa",
        headers={**auth_headers(admin_id), "Idempotency-Key": str(uuid.uuid4())},
        json={
            "merchant_id": str(merchant_id),
            "amount": "1000.00",
            "destination_name": "Jane Doe",
            "destination_identifier": "+255700000000",
        },
    )

    assert response.status_code == 202, response.text
    assert response.json()["data"]["method"] == "SELCOM_PESA"


def test_bank_account_disbursement_requires_bank_name(fake_client):
    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "10000.00")

    response = client.post(
        "/v1/disbursements/bank-account",
        headers={**auth_headers(admin_id), "Idempotency-Key": str(uuid.uuid4())},
        json={
            "merchant_id": str(merchant_id),
            "amount": "1000.00",
            "destination_name": "Jane Doe",
            "destination_identifier": "0123456789",
        },
    )

    assert response.status_code == 422


def test_bank_account_disbursement_success(fake_client):
    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "10000.00")

    response = client.post(
        "/v1/disbursements/bank-account",
        headers={**auth_headers(admin_id), "Idempotency-Key": str(uuid.uuid4())},
        json={
            "merchant_id": str(merchant_id),
            "amount": "1000.00",
            "destination_name": "Jane Doe",
            "destination_identifier": "0123456789",
            "bank_name": "CRDB Bank",
        },
    )

    assert response.status_code == 202, response.text
    assert response.json()["data"]["bank_name"] == "CRDB Bank"


def test_disbursement_is_idempotent_on_retry(fake_client):
    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "10000.00")
    headers = {**auth_headers(admin_id), "Idempotency-Key": "retry-key"}
    body = {
        "merchant_id": str(merchant_id),
        "amount": "1000.00",
        "destination_name": "Jane Doe",
        "destination_identifier": "+255700000000",
    }

    first = client.post("/v1/disbursements/mobile-money", headers=headers, json=body)
    second = client.post("/v1/disbursements/mobile-money", headers=headers, json=body)

    assert first.status_code == second.status_code == 202
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    assert len(fake_client.table("disbursements")._table.rows) == 1
    # Only actually deducted once, not once per retry.
    assert _wallet_balance(fake_client, merchant_id) == Decimal("9000.00")


# --- provider failure reverses the reservation ------------------------------


def test_failed_disbursement_reverses_reservation(fake_client, monkeypatch):
    merchant_id, admin_id = _merchant_and_admin(fake_client, webhook_url="https://merchant.example.com/hooks")
    _fund_wallet(fake_client, merchant_id, "10000.00")

    monkeypatch.setenv("MOCK_PROVIDER_FAILURE_RATE", "1")
    get_settings.cache_clear()
    get_selcom_client.cache_clear()

    response = _request_mobile_money(merchant_id, admin_id, "4000.00")

    assert response.status_code == 202, response.text
    body = response.json()["data"]
    assert body["status"] == "FAILED"

    # Reserved, then reversed: balance ends back where it started.
    assert _wallet_balance(fake_client, merchant_id) == Decimal("10000.00")

    transaction = next(
        t for t in fake_client.table("transactions")._table.rows if t["disbursement_id"] == body["id"]
    )
    assert transaction["status"] == "reversed"

    entries = [
        e for e in fake_client.table("ledger_entries")._table.rows if e["transaction_id"] == transaction["id"]
    ]
    assert len(entries) == 4
    debits = sum(Decimal(e["amount"]) for e in entries if e["direction"] == "debit")
    credits = sum(Decimal(e["amount"]) for e in entries if e["direction"] == "credit")
    assert debits == credits

    events = fake_client.table("webhook_events")._table.rows
    assert any(e["event_name"] == "disbursement.failed" for e in events)


def test_immediate_provider_exception_reverses_reservation(fake_client, monkeypatch):
    """Regression test: _reserve_and_run_disbursement_provider used to have
    no try/except around provider.initiate_disbursement() — an outright
    provider-call failure (e.g. a live Selcom timeout, surfaced as
    SelcomAPIError) propagated unhandled, leaving the wallet debited and
    the disbursement stuck PROCESSING forever. It must now be caught,
    reversed, and reported as a normal FAILED withdrawal — not a 502."""
    import app.services.disbursements as disbursements_module
    from app.core.errors import SelcomAPIError

    merchant_id, admin_id = _merchant_and_admin(fake_client, webhook_url="https://merchant.example.com/hooks")
    _fund_wallet(fake_client, merchant_id, "10000.00")

    class _RaisingProvider:
        async def initiate_disbursement(self, **kwargs):
            raise SelcomAPIError("Could not reach Selcom (TimeoutException)")

    monkeypatch.setattr(disbursements_module, "get_selcom_client", lambda: _RaisingProvider())

    response = _request_mobile_money(merchant_id, admin_id, "4000.00")

    assert response.status_code == 202, response.text
    body = response.json()["data"]
    assert body["status"] == "FAILED"

    # Reserved, then reversed: balance ends back where it started.
    assert _wallet_balance(fake_client, merchant_id) == Decimal("10000.00")

    transaction = next(
        t for t in fake_client.table("transactions")._table.rows if t["disbursement_id"] == body["id"]
    )
    assert transaction["status"] == "reversed"

    audit_events = [a for a in fake_client.table("audit_logs")._table.rows if a["action"] == "disbursement.failed"]
    assert len(audit_events) == 1
    assert audit_events[0]["actor_type"] == "system"

    notifications = fake_client.table("notifications")._table.rows
    assert any(n["notification_type"] == "withdrawal_failed" for n in notifications)

    events = fake_client.table("webhook_events")._table.rows
    assert any(e["event_name"] == "disbursement.failed" for e in events)


def test_provider_processing_result_leaves_disbursement_processing(fake_client, monkeypatch):
    """A real Selcom payout may not resolve synchronously — treated the
    same way collections handle "processing": the disbursement stays
    PROCESSING (not incorrectly reversed as if it were a rejection), ready
    for resolve_disbursement_from_callback to finish later."""
    import app.services.disbursements as disbursements_module
    from app.services.disbursements import resolve_disbursement_from_callback
    from app.services.selcom.schemas import DisbursementResult

    merchant_id, admin_id = _merchant_and_admin(fake_client, webhook_url="https://merchant.example.com/hooks")
    _fund_wallet(fake_client, merchant_id, "10000.00")

    class _ProcessingProvider:
        async def initiate_disbursement(self, **kwargs):
            return DisbursementResult(provider="selcom", provider_reference="SEL-PROC-1", status="processing")

    monkeypatch.setattr(disbursements_module, "get_selcom_client", lambda: _ProcessingProvider())

    response = _request_mobile_money(merchant_id, admin_id, "4000.00")

    assert response.status_code == 202, response.text
    body = response.json()["data"]
    assert body["status"] == "PROCESSING"
    assert body["provider_reference"] == "SEL-PROC-1"
    # Reserved, and left reserved — not reversed just because it's not resolved yet.
    assert _wallet_balance(fake_client, merchant_id) == Decimal("6000.00")

    resolved = resolve_disbursement_from_callback(
        fake_client, provider_reference="SEL-PROC-1", status="successful", failure_reason=None
    )
    assert resolved["status"] == "SUCCESS"
    assert _wallet_balance(fake_client, merchant_id) == Decimal("6000.00")


# --- high-value approval queue -----------------------------------------------


def test_high_value_disbursement_requires_approval_then_approve(fake_client):
    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "10000000.00")

    response = _request_mobile_money(merchant_id, admin_id, "5000000.00")

    assert response.status_code == 202, response.text
    body = response.json()["data"]
    assert body["status"] == "PENDING"
    assert body["requires_approval"] is True
    assert body["provider_reference"] is None
    # Not reserved yet — approval hasn't happened.
    assert _wallet_balance(fake_client, merchant_id) == Decimal("10000000.00")

    super_admin_id = uuid.uuid4()
    make_super_admin(fake_client, super_admin_id)

    approve_response = client.post(
        f"/v1/disbursements/{body['id']}/approve", headers=auth_headers(super_admin_id)
    )

    assert approve_response.status_code == 200
    approved = approve_response.json()["data"]
    assert approved["status"] == "SUCCESS"
    assert approved["approved_by"] == str(super_admin_id)
    assert _wallet_balance(fake_client, merchant_id) == Decimal("5000000.00")


def test_reject_disbursement(fake_client):
    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "10000000.00")

    body = _request_mobile_money(merchant_id, admin_id, "5000000.00").json()["data"]

    super_admin_id = uuid.uuid4()
    make_super_admin(fake_client, super_admin_id)

    reject_response = client.post(f"/v1/disbursements/{body['id']}/reject", headers=auth_headers(super_admin_id))

    assert reject_response.status_code == 200
    rejected = reject_response.json()["data"]
    assert rejected["status"] == "FAILED"
    # Never reserved, so nothing to give back.
    assert _wallet_balance(fake_client, merchant_id) == Decimal("10000000.00")


def test_approve_rejects_non_pending_disbursement(fake_client):
    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "10000.00")
    body = _request_mobile_money(merchant_id, admin_id, "1000.00").json()["data"]

    super_admin_id = uuid.uuid4()
    make_super_admin(fake_client, super_admin_id)

    response = client.post(f"/v1/disbursements/{body['id']}/approve", headers=auth_headers(super_admin_id))

    assert response.status_code == 409


# --- list / get ----------------------------------------------------------------


def test_list_disbursements_is_scoped_to_merchant_id_query_param(fake_client):
    merchant_id, admin_id = _merchant_and_admin(fake_client)
    other_merchant_id, other_admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "10000.00")
    _fund_wallet(fake_client, other_merchant_id, "10000.00")

    _request_mobile_money(merchant_id, admin_id, "1000.00")
    _request_mobile_money(other_merchant_id, other_admin_id, "1000.00")

    response = client.get(
        "/v1/disbursements", headers=auth_headers(admin_id), params={"merchant_id": str(merchant_id)}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["merchant_id"] == str(merchant_id)


def test_get_disbursement_not_found(fake_client):
    _merchant_id, admin_id = _merchant_and_admin(fake_client)

    response = client.get(f"/v1/disbursements/{uuid.uuid4()}", headers=auth_headers(admin_id))

    assert response.status_code == 404


def test_get_disbursement_rejects_non_member(fake_client):
    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "10000.00")
    body = _request_mobile_money(merchant_id, admin_id, "1000.00").json()["data"]

    outsider_id = uuid.uuid4()
    response = client.get(f"/v1/disbursements/{body['id']}", headers=auth_headers(outsider_id))

    assert response.status_code == 403
