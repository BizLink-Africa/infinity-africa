"""Withdrawal (disbursement) creation: balance validation against the fee
snapshot, the fee snapshot itself, idempotency, and list/get scoping — end
to end against the in-memory FakeSupabaseClient (see tests/fakes.py).

Every withdrawal now lands PENDING_ADMIN_APPROVAL regardless of amount —
there is no more auto-processing branch. Selcom/ledger reservation only
ever happens once a Super Admin approves (see tests/test_admin_withdrawals.py
for the approve/reject/request-info/refresh-status/reconcile-pending
coverage, which moved to /v1/admin/withdrawals/* along with the routes).
"""

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from tests.factories import (
    TEST_JWT_SECRET,
    auth_headers,
    create_merchant,
    create_pricing_rule,
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


def _merchant_and_admin(fake_client, **merchant_overrides):
    merchant = create_merchant(fake_client, **merchant_overrides)
    merchant_id = uuid.UUID(merchant["id"])
    admin_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, admin_id, "MERCHANT_ADMIN")
    return merchant_id, admin_id


def _fund_wallet(fake_client, merchant_id: uuid.UUID, amount: str, currency: str = "TZS") -> None:
    """Seeds a merchant_wallet ledger_accounts row directly, so a
    withdrawal test doesn't need to run a whole collection first just to
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
        "destination_code": "MPESA",
        **overrides,
    }
    return client.post(
        "/v1/disbursements/mobile-money",
        headers={**auth_headers(admin_id), "Idempotency-Key": str(uuid.uuid4())},
        json=body,
    )


# --- ENABLE_WITHDRAWALS kill switch -------------------------------------------


def test_withdrawal_request_blocked_when_withdrawals_disabled(fake_client, monkeypatch):
    """ENABLE_WITHDRAWALS=false (app/core/feature_flags.py) must block new
    withdrawal requests without touching balance/verification checks —
    it's the first thing checked."""
    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "10000.00")
    monkeypatch.setenv("ENABLE_WITHDRAWALS", "false")
    get_settings.cache_clear()

    response = _request_mobile_money(merchant_id, admin_id, "1000.00")

    assert response.status_code == 503, response.text
    assert response.json()["error"]["code"] == "feature_disabled"
    assert fake_client.table("disbursements")._table.rows == []
    assert _wallet_balance(fake_client, merchant_id) == Decimal("10000.00")


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


# --- backend-controlled withdrawal amount limits (MVP launch) ---------------
# Supersedes the old, temporary WITHDRAWAL_PILOT_MODE/
# WITHDRAWAL_PILOT_MAX_AMOUNT_TZS pilot cap
# (docs/withdrawal-production-pilot-checklist.md) — see
# Settings.min_withdrawal_amount_tzs/max_withdrawal_amount_tzs/
# daily_withdrawal_limit_tzs and
# app/services/disbursements.py::_check_withdrawal_amount_limits.


def test_withdrawal_below_minimum_amount_is_rejected(fake_client, monkeypatch):
    monkeypatch.setenv("MIN_WITHDRAWAL_AMOUNT_TZS", "1000")
    get_settings.cache_clear()

    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "10000.00")

    response = _request_mobile_money(merchant_id, admin_id, "500.00")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "withdrawal_restricted"
    assert "Minimum" in response.json()["error"]["message"]
    assert fake_client.table("disbursements")._table.rows == []
    assert _wallet_balance(fake_client, merchant_id) == Decimal("10000.00")


def test_withdrawal_at_exactly_minimum_amount_is_allowed(fake_client, monkeypatch):
    monkeypatch.setenv("MIN_WITHDRAWAL_AMOUNT_TZS", "1000")
    get_settings.cache_clear()

    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "10000.00")

    response = _request_mobile_money(merchant_id, admin_id, "1000.00")

    assert response.status_code == 202, response.text
    assert response.json()["data"]["status"] == "PENDING_ADMIN_APPROVAL"


def test_withdrawal_above_maximum_amount_is_rejected(fake_client, monkeypatch):
    monkeypatch.setenv("MAX_WITHDRAWAL_AMOUNT_TZS", "5000000")
    get_settings.cache_clear()

    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "100000000.00")

    response = _request_mobile_money(merchant_id, admin_id, "5000001.00")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "withdrawal_restricted"
    assert "Maximum" in response.json()["error"]["message"]
    assert fake_client.table("disbursements")._table.rows == []


def test_withdrawal_at_exactly_maximum_amount_is_allowed(fake_client, monkeypatch):
    monkeypatch.setenv("MAX_WITHDRAWAL_AMOUNT_TZS", "5000000")
    get_settings.cache_clear()

    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "100000000.00")

    response = _request_mobile_money(merchant_id, admin_id, "5000000.00")

    assert response.status_code == 202, response.text
    assert response.json()["data"]["status"] == "PENDING_ADMIN_APPROVAL"


def test_large_withdrawal_within_limits_still_lands_pending_approval(fake_client, monkeypatch):
    """A large amount, even right up against the configured max, still
    always requires Super Admin approval — there is no auto-processing
    branch regardless of amount."""
    monkeypatch.setenv("MAX_WITHDRAWAL_AMOUNT_TZS", "5000000")
    get_settings.cache_clear()

    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "100000000.00")

    response = _request_mobile_money(merchant_id, admin_id, "4999999.00")

    assert response.status_code == 202, response.text
    assert response.json()["data"]["status"] == "PENDING_ADMIN_APPROVAL"
    assert response.json()["data"]["approved_by"] is None


def test_daily_withdrawal_limit_blocks_cumulative_total(fake_client, monkeypatch):
    """Two requests that individually fit under the per-request max can
    still be blocked together once their sum crosses the rolling 24-hour
    cap."""
    monkeypatch.setenv("DAILY_WITHDRAWAL_LIMIT_TZS", "10000")
    get_settings.cache_clear()

    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "1000000.00")

    first = _request_mobile_money(merchant_id, admin_id, "6000.00")
    assert first.status_code == 202, first.text

    second = _request_mobile_money(merchant_id, admin_id, "5000.00")

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "withdrawal_restricted"
    assert "daily withdrawal limit" in second.json()["error"]["message"]
    # Only the first request was ever written.
    assert len(fake_client.table("disbursements")._table.rows) == 1


def test_daily_withdrawal_limit_allows_requests_at_exactly_the_cap(fake_client, monkeypatch):
    monkeypatch.setenv("DAILY_WITHDRAWAL_LIMIT_TZS", "10000")
    get_settings.cache_clear()

    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "1000000.00")

    first = _request_mobile_money(merchant_id, admin_id, "6000.00")
    second = _request_mobile_money(merchant_id, admin_id, "4000.00")

    assert first.status_code == 202, first.text
    assert second.status_code == 202, second.text


def test_daily_withdrawal_limit_excludes_rejected_requests(fake_client, monkeypatch):
    """A rejected withdrawal never moved money, so it must not count
    against the same merchant's remaining daily allowance."""
    monkeypatch.setenv("DAILY_WITHDRAWAL_LIMIT_TZS", "10000")
    get_settings.cache_clear()

    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "1000000.00")
    super_admin_id = uuid.uuid4()
    make_super_admin(fake_client, super_admin_id)

    first = _request_mobile_money(merchant_id, admin_id, "9000.00")
    assert first.status_code == 202, first.text
    first_id = first.json()["data"]["id"]

    rejected = client.post(
        f"/v1/admin/withdrawals/{first_id}/reject",
        headers=auth_headers(super_admin_id),
        json={"rejection_reason": "Testing daily-limit exclusion"},
    )
    assert rejected.status_code == 200, rejected.text

    second = _request_mobile_money(merchant_id, admin_id, "9000.00")

    assert second.status_code == 202, second.text


def test_daily_withdrawal_limit_is_scoped_per_merchant(fake_client, monkeypatch):
    monkeypatch.setenv("DAILY_WITHDRAWAL_LIMIT_TZS", "10000")
    get_settings.cache_clear()

    merchant_a, admin_a = _merchant_and_admin(fake_client)
    merchant_b, admin_b = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_a, "1000000.00")
    _fund_wallet(fake_client, merchant_b, "1000000.00")

    first = _request_mobile_money(merchant_a, admin_a, "9000.00")
    second = _request_mobile_money(merchant_b, admin_b, "9000.00")

    assert first.status_code == 202, first.text
    assert second.status_code == 202, second.text


# --- insufficient balance (checked against total_reserved_amount) -----------


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

    response = _request_mobile_money(merchant_id, admin_id, "1000.00")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_balance"


def test_balance_check_includes_fee_not_just_principal(fake_client):
    """A merchant with just enough for the principal but not the fee on
    top of it must still be rejected — total_reserved_amount, not amount,
    is what's checked against available balance."""
    merchant_id, admin_id = _merchant_and_admin(fake_client)
    create_pricing_rule(fake_client, merchant_id=merchant_id, flat_fee="200")
    _fund_wallet(fake_client, merchant_id, "1100.00")

    response = _request_mobile_money(merchant_id, admin_id, "1000.00")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_balance"


# --- every withdrawal lands PENDING_ADMIN_APPROVAL ---------------------------


def test_withdrawal_request_creates_pending_admin_approval_and_never_calls_selcom(fake_client, monkeypatch):
    import app.services.disbursements as disbursements_module

    def _fail(*args, **kwargs):
        raise AssertionError("get_selcom_business_client must never be called from the merchant submission path")

    monkeypatch.setattr(disbursements_module, "get_selcom_business_client", _fail)

    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "10000.00")

    response = _request_mobile_money(merchant_id, admin_id, "4000.00")

    assert response.status_code == 202, response.text
    body = response.json()["data"]
    assert body["status"] == "PENDING_ADMIN_APPROVAL"
    assert body["requires_approval"] is True
    assert body["provider_reference"] is None

    # Not reserved yet — nothing happens until a Super Admin approves.
    assert _wallet_balance(fake_client, merchant_id) == Decimal("10000.00")
    assert fake_client.table("transactions")._table.rows == []


def test_withdrawal_stores_fee_snapshot(fake_client):
    merchant_id, admin_id = _merchant_and_admin(fake_client)
    create_pricing_rule(
        fake_client,
        merchant_id=merchant_id,
        percentage_fee="1",
        flat_fee="500",
        processor_fee_flat="300",
        processor_fee_pass_through=True,
        label="Negotiated rate",
    )
    _fund_wallet(fake_client, merchant_id, "1000000.00")

    body = _request_mobile_money(merchant_id, admin_id, "100000.00").json()["data"]

    assert Decimal(body["percentage_fee_component"]) == Decimal("1000.00")
    assert Decimal(body["flat_fee_component"]) == Decimal("500.00")
    assert Decimal(body["infinity_fee"]) == Decimal("1500.00")
    assert Decimal(body["processor_charge"]) == Decimal("300.00")
    assert Decimal(body["total_charges"]) == Decimal("1800.00")
    assert Decimal(body["total_reserved_amount"]) == Decimal("101800.00")
    assert Decimal(body["recipient_net_amount"]) == Decimal("100000.00")
    assert body["pricing_snapshot_json"]["pricing_rule_label"] == "Negotiated rate"


def test_later_pricing_change_does_not_affect_already_submitted_withdrawal(fake_client):
    merchant_id, admin_id = _merchant_and_admin(fake_client)
    rule = create_pricing_rule(fake_client, merchant_id=merchant_id, percentage_fee="1")
    _fund_wallet(fake_client, merchant_id, "1000000.00")

    body = _request_mobile_money(merchant_id, admin_id, "100000.00").json()["data"]
    assert Decimal(body["infinity_fee"]) == Decimal("1000.00")

    # Admin edits the rule after the withdrawal was already submitted.
    for row in fake_client.table("merchant_pricing_rules")._table.rows:
        if row["id"] == rule["id"]:
            row["percentage_fee"] = "10"

    refetched = client.get(f"/v1/disbursements/{body['id']}", headers=auth_headers(admin_id)).json()["data"]
    assert Decimal(refetched["infinity_fee"]) == Decimal("1000.00")


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
            "destination_code": "SELCOM",
        },
    )

    assert response.status_code == 202, response.text
    body = response.json()["data"]
    assert body["method"] == "SELCOM_PESA"
    assert body["status"] == "PENDING_ADMIN_APPROVAL"


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
            "destination_code": "CRDB",
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
            "destination_code": "CRDB",
        },
    )

    assert response.status_code == 202, response.text
    body = response.json()["data"]
    assert body["bank_name"] == "CRDB Bank"
    assert body["status"] == "PENDING_ADMIN_APPROVAL"


def test_disbursement_is_idempotent_on_retry(fake_client):
    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "10000.00")
    headers = {**auth_headers(admin_id), "Idempotency-Key": "retry-key"}
    body = {
        "merchant_id": str(merchant_id),
        "amount": "1000.00",
        "destination_name": "Jane Doe",
        "destination_identifier": "+255700000000",
        "destination_code": "MPESA",
    }

    first = client.post("/v1/disbursements/mobile-money", headers=headers, json=body)
    second = client.post("/v1/disbursements/mobile-money", headers=headers, json=body)

    assert first.status_code == second.status_code == 202
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    assert len(fake_client.table("disbursements")._table.rows) == 1
    # Nothing is reserved before approval, retried or not.
    assert _wallet_balance(fake_client, merchant_id) == Decimal("10000.00")


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
