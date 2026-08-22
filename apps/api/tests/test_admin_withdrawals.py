"""Super Admin withdrawal review — /v1/admin/withdrawals/* (approve, reject,
request-info, refresh-status, reconcile-pending). Every withdrawal starts
PENDING_ADMIN_APPROVAL (see tests/test_disbursements.py for the
creation/fee-snapshot coverage); this file is what happens next. Selcom is
only ever reached via approve — nothing here or in disbursements.py calls
it from anywhere else.

Approval calls the Selcom Business Disbursement API client
(app/services/selcom_business/), not the checkout/collections one — every
fixture here runs with SELCOM_BUSINESS_MODE=mock so approve/refresh/
reconcile never attempt a real network call.
"""

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services.selcom_business.client import get_selcom_business_client
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
    monkeypatch.setenv("SELCOM_BUSINESS_MODE", "mock")
    monkeypatch.setenv("MOCK_PROVIDER_FAILURE_RATE", "0")
    monkeypatch.setenv("MOCK_PROVIDER_LATENCY_SECONDS", "0")
    get_settings.cache_clear()
    get_selcom_business_client.cache_clear()
    yield
    get_settings.cache_clear()
    get_selcom_business_client.cache_clear()


def _merchant_and_admin(fake_client, **merchant_overrides):
    merchant = create_merchant(fake_client, **merchant_overrides)
    merchant_id = uuid.UUID(merchant["id"])
    admin_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, admin_id, "MERCHANT_ADMIN")
    return merchant_id, admin_id


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


def _request_withdrawal(merchant_id: uuid.UUID, admin_id: uuid.UUID, amount: str, **overrides) -> dict:
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
    return response.json()["data"]


def _approve(withdrawal_id: str, super_admin_id: uuid.UUID):
    return client.post(f"/v1/admin/withdrawals/{withdrawal_id}/approve", headers=auth_headers(super_admin_id))


def _reject(withdrawal_id: str, super_admin_id: uuid.UUID, reason: str = "Suspicious destination account"):
    return client.post(
        f"/v1/admin/withdrawals/{withdrawal_id}/reject",
        headers=auth_headers(super_admin_id),
        json={"rejection_reason": reason},
    )


# --- approve -------------------------------------------------------------------


def test_approve_reserves_funds_and_calls_selcom(fake_client):
    merchant_id, admin_id = _merchant_and_admin(fake_client, webhook_url="https://merchant.example.com/hooks")
    _fund_wallet(fake_client, merchant_id, "10000000.00")
    body = _request_withdrawal(merchant_id, admin_id, "5000000.00")
    assert _wallet_balance(fake_client, merchant_id) == Decimal("10000000.00")  # not reserved yet

    super_admin_id = uuid.uuid4()
    make_super_admin(fake_client, super_admin_id)

    response = _approve(body["id"], super_admin_id)

    assert response.status_code == 200, response.text
    approved = response.json()["data"]
    assert approved["status"] == "SUCCESS"
    assert approved["approved_by"] == str(super_admin_id)
    assert approved["provider_reference"] is not None
    assert _wallet_balance(fake_client, merchant_id) == Decimal("5000000.00")

    transaction = next(
        t for t in fake_client.table("transactions")._table.rows if t["disbursement_id"] == body["id"]
    )
    assert transaction["status"] == "successful"
    events = fake_client.table("webhook_events")._table.rows
    assert any(e["event_name"] == "disbursement.success" for e in events)


def test_approve_uses_stored_snapshot_not_a_recalculation(fake_client):
    from tests.factories import create_pricing_rule

    merchant_id, admin_id = _merchant_and_admin(fake_client)
    rule = create_pricing_rule(fake_client, merchant_id=merchant_id, percentage_fee="1")
    _fund_wallet(fake_client, merchant_id, "1000000.00")
    body = _request_withdrawal(merchant_id, admin_id, "100000.00")
    assert Decimal(body["infinity_fee"]) == Decimal("1000.00")

    # Mutate the rule after submission but before approval.
    for row in fake_client.table("merchant_pricing_rules")._table.rows:
        if row["id"] == rule["id"]:
            row["percentage_fee"] = "50"

    super_admin_id = uuid.uuid4()
    make_super_admin(fake_client, super_admin_id)
    _approve(body["id"], super_admin_id).json()["data"]

    # Reserved exactly what was frozen at submission (100000 + 1000 fee),
    # not a recalculated 50% fee.
    assert _wallet_balance(fake_client, merchant_id) == Decimal("1000000.00") - Decimal("101000.00")


def test_duplicate_approval_does_not_double_send_to_selcom(fake_client):
    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "10000.00")
    body = _request_withdrawal(merchant_id, admin_id, "1000.00")

    super_admin_id = uuid.uuid4()
    make_super_admin(fake_client, super_admin_id)

    first = _approve(body["id"], super_admin_id)
    assert first.status_code == 200
    balance_after_first = _wallet_balance(fake_client, merchant_id)

    second = _approve(body["id"], super_admin_id)

    assert second.status_code == 409
    # Balance unchanged by the rejected second approval attempt.
    assert _wallet_balance(fake_client, merchant_id) == balance_after_first


def test_approve_stores_raw_selcom_response(fake_client, monkeypatch):
    """The full raw Selcom response body — not just the parsed
    transId/receipt/status — must land on the disbursement row."""
    import app.services.disbursements as disbursements_module
    from app.services.selcom_business.schemas import SelcomBusinessResult

    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "10000.00")
    body = _request_withdrawal(merchant_id, admin_id, "1000.00")

    raw_response = {"status": "success", "transId": "SEL-RAW-1", "receipt": "RCPT-RAW-1", "extra_field": "kept"}

    class _RawResponseProvider:
        async def process_transaction(self, **kwargs):
            return SelcomBusinessResult(
                transaction_id="SEL-RAW-1", status="successful", receipt="RCPT-RAW-1", raw_response=raw_response
            )

    monkeypatch.setattr(disbursements_module, "get_selcom_business_client", lambda: _RawResponseProvider())

    super_admin_id = uuid.uuid4()
    make_super_admin(fake_client, super_admin_id)
    response = _approve(body["id"], super_admin_id)

    assert response.status_code == 200, response.text
    assert response.json()["data"]["selcom_raw_response"] == raw_response


def test_bank_account_recipient_is_never_phone_normalized_at_approval(fake_client, monkeypatch):
    """Bank account numbers must reach Selcom exactly as the merchant gave
    them — normalize_tz_phone must never touch destination_identifier for a
    BANK_ACCOUNT withdrawal, at submission or at approval time."""
    import app.services.disbursements as disbursements_module

    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "10000.00")

    bank_account_number = "0151234567890123"  # not phone-shaped, would be mangled by normalize_tz_phone
    body_response = client.post(
        "/v1/disbursements/bank-account",
        headers={**auth_headers(admin_id), "Idempotency-Key": str(uuid.uuid4())},
        json={
            "merchant_id": str(merchant_id),
            "amount": "1000.00",
            "destination_name": "Jane Doe",
            "destination_identifier": bank_account_number,
            "destination_code": "CRDB",
            "bank_name": "CRDB Bank",
        },
    )
    assert body_response.status_code == 202, body_response.text
    body = body_response.json()["data"]
    assert body["destination_identifier"] == bank_account_number

    captured: dict = {}

    class _CapturingProvider:
        async def process_transaction(self, **kwargs):
            captured.update(kwargs)
            from app.services.selcom_business.schemas import SelcomBusinessResult

            return SelcomBusinessResult(transaction_id="SEL-BANK-1", status="successful")

    monkeypatch.setattr(disbursements_module, "get_selcom_business_client", lambda: _CapturingProvider())

    super_admin_id = uuid.uuid4()
    make_super_admin(fake_client, super_admin_id)
    response = _approve(body["id"], super_admin_id)

    assert response.status_code == 200, response.text
    assert captured["recipient_account"] == bank_account_number


def test_completed_withdrawal_cannot_be_rejected(fake_client):
    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "10000.00")
    body = _request_withdrawal(merchant_id, admin_id, "1000.00")

    super_admin_id = uuid.uuid4()
    make_super_admin(fake_client, super_admin_id)
    _approve(body["id"], super_admin_id)

    response = _reject(body["id"], super_admin_id)
    assert response.status_code == 409


def test_provider_failure_reverses_reservation(fake_client, monkeypatch):
    merchant_id, admin_id = _merchant_and_admin(fake_client, webhook_url="https://merchant.example.com/hooks")
    _fund_wallet(fake_client, merchant_id, "10000.00")
    body = _request_withdrawal(merchant_id, admin_id, "4000.00")

    monkeypatch.setenv("MOCK_PROVIDER_FAILURE_RATE", "1")
    get_settings.cache_clear()
    get_selcom_business_client.cache_clear()

    super_admin_id = uuid.uuid4()
    make_super_admin(fake_client, super_admin_id)
    response = _approve(body["id"], super_admin_id)

    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "FAILED"
    assert _wallet_balance(fake_client, merchant_id) == Decimal("10000.00")

    # Regression: _fail_and_reverse must persist the failure reason onto
    # admin_status_reason (previously only reached the audit log/merchant
    # notification, never the row itself — found via a real Selcom sandbox
    # rejection during end-to-end testing, see docs/selcom-sandbox-test-accounts.md).
    assert response.json()["data"]["admin_status_reason"] in (
        "Invalid recipient account",
        "Provider network timeout",
        "Payout limit exceeded",
    )

    transaction = next(
        t for t in fake_client.table("transactions")._table.rows if t["disbursement_id"] == body["id"]
    )
    assert transaction["status"] == "reversed"
    entries = [
        e for e in fake_client.table("ledger_entries")._table.rows if e["transaction_id"] == transaction["id"]
    ]
    assert sum(Decimal(e["amount"]) for e in entries if e["direction"] == "debit") == sum(
        Decimal(e["amount"]) for e in entries if e["direction"] == "credit"
    )
    assert any(e["event_name"] == "disbursement.failed" for e in fake_client.table("webhook_events")._table.rows)


def test_immediate_provider_exception_reverses_reservation(fake_client, monkeypatch):
    """Regression test: an outright provider-call failure (e.g. a live
    Selcom timeout, surfaced as SelcomAPIError) must be caught, reversed,
    and reported as a normal FAILED withdrawal — not an unhandled 502 with
    money stuck reserved."""
    import app.services.disbursements as disbursements_module
    from app.core.errors import SelcomAPIError

    merchant_id, admin_id = _merchant_and_admin(fake_client, webhook_url="https://merchant.example.com/hooks")
    _fund_wallet(fake_client, merchant_id, "10000.00")
    body = _request_withdrawal(merchant_id, admin_id, "4000.00")

    class _RaisingProvider:
        async def process_transaction(self, **kwargs):
            raise SelcomAPIError("Could not reach Selcom Business API (TimeoutException)")

    monkeypatch.setattr(disbursements_module, "get_selcom_business_client", lambda: _RaisingProvider())

    super_admin_id = uuid.uuid4()
    make_super_admin(fake_client, super_admin_id)
    response = _approve(body["id"], super_admin_id)

    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "FAILED"
    assert _wallet_balance(fake_client, merchant_id) == Decimal("10000.00")
    # Same admin_status_reason regression as test_provider_failure_reverses_reservation
    # above, exercised via the SelcomAPIError branch instead of a clean
    # result.status == "failed" — str(exc) is the message passed to SelcomAPIError().
    assert response.json()["data"]["admin_status_reason"] == "Could not reach Selcom Business API (TimeoutException)"

    audit_events = [a for a in fake_client.table("audit_logs")._table.rows if a["action"] == "disbursement.failed"]
    assert len(audit_events) == 1
    assert audit_events[0]["actor_type"] == "system"
    notifications = fake_client.table("notifications")._table.rows
    assert any(n["notification_type"] == "withdrawal_failed" for n in notifications)


def test_provider_exception_with_response_body_stores_raw_response(fake_client, monkeypatch):
    """Regression test: when Selcom rejects a request with a parseable
    error body (SelcomAPIError.provider_response_body — see
    app/services/selcom_business/live_client.py), that body must reach
    disbursements.selcom_raw_response, not be silently dropped. Found via a
    real Selcom sandbox HTTP 400 during end-to-end testing (see
    docs/selcom-sandbox-test-accounts.md) — previously _fail_and_reverse
    was called without raw_response at all on this path."""
    import app.services.disbursements as disbursements_module
    from app.core.errors import SelcomAPIError

    merchant_id, admin_id = _merchant_and_admin(fake_client, webhook_url="https://merchant.example.com/hooks")
    _fund_wallet(fake_client, merchant_id, "10000.00")
    body = _request_withdrawal(merchant_id, admin_id, "4000.00")

    error_body = {
        "success": False,
        "error_code": -40,
        "message": "Invalid account number for the provided bank/FI code.",
        "result": "FAIL",
        "resultcode": "-40",
        "data": [],
    }

    class _RaisingWithBodyProvider:
        async def process_transaction(self, **kwargs):
            raise SelcomAPIError(
                "Selcom Business API returned HTTP 400 for /transaction/process",
                provider_status_code=400,
                provider_response_body=error_body,
            )

    monkeypatch.setattr(disbursements_module, "get_selcom_business_client", lambda: _RaisingWithBodyProvider())

    super_admin_id = uuid.uuid4()
    make_super_admin(fake_client, super_admin_id)
    response = _approve(body["id"], super_admin_id)

    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "FAILED"
    assert response.json()["data"]["selcom_raw_response"] == error_body


def test_selcom_raw_response_save_failure_still_reaches_failed_status(fake_client, monkeypatch):
    """Regression test: this happened for real in production —
    selcom_raw_response was missing from the database (a migration that
    was never applied), so _fail_and_reverse crashed with a 500 partway
    through its update, after the ledger reversal had already run and
    could not be undone. The disbursement was left stuck at PROCESSING
    forever, with retry-approve and refresh-status both 409ing. A failure
    to save selcom_raw_response specifically must never again block
    reaching the terminal FAILED status — see
    docs/withdrawal-pricing-and-approval.md."""
    import app.services.disbursements as disbursements_module
    from app.core.errors import SelcomAPIError
    from app.services.crud import update_row as real_update_row

    merchant_id, admin_id = _merchant_and_admin(fake_client, webhook_url="https://merchant.example.com/hooks")
    _fund_wallet(fake_client, merchant_id, "10000.00")
    body = _request_withdrawal(merchant_id, admin_id, "4000.00")

    class _RaisingWithBodyProvider:
        async def process_transaction(self, **kwargs):
            raise SelcomAPIError(
                "Selcom Business API returned HTTP 400 for /transaction/process",
                provider_status_code=400,
                provider_response_body={"success": False, "message": "Invalid account."},
            )

    monkeypatch.setattr(disbursements_module, "get_selcom_business_client", lambda: _RaisingWithBodyProvider())

    def _update_row_missing_raw_response_column(client, table, row_id, data, **kwargs):
        if table == "disbursements" and "selcom_raw_response" in data:
            raise RuntimeError(
                "{'message': \"Could not find the 'selcom_raw_response' column of 'disbursements' "
                "in the schema cache\", 'code': 'PGRST204'}"
            )
        return real_update_row(client, table, row_id, data, **kwargs)

    monkeypatch.setattr(disbursements_module, "update_row", _update_row_missing_raw_response_column)

    super_admin_id = uuid.uuid4()
    make_super_admin(fake_client, super_admin_id)
    response = _approve(body["id"], super_admin_id)

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "FAILED"
    assert data["admin_status_reason"] == "Selcom Business API returned HTTP 400 for /transaction/process"
    # Never actually saved (the whole point of this test) — falsy either
    # way the fixture's unset-jsonb-column default renders it (None or {}).
    assert not data["selcom_raw_response"]
    assert _wallet_balance(fake_client, merchant_id) == Decimal("10000.00")


def test_blocked_ip_whitelist_does_not_reverse_reservation(fake_client, monkeypatch):
    """A 403 from Selcom (IP not whitelisted — Selcom's own error code 611)
    is an operator problem, not a payout failure — funds stay reserved
    pending a fix + refresh/retry."""
    import app.services.disbursements as disbursements_module
    from app.core.errors import SelcomAPIError

    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "10000.00")
    body = _request_withdrawal(merchant_id, admin_id, "4000.00")

    class _BlockedProvider:
        async def process_transaction(self, **kwargs):
            raise SelcomAPIError(
                "Selcom returned HTTP 403 (611: IP not whitelisted)",
                provider_status_code=403,
                is_ip_whitelist_error=True,
            )

    monkeypatch.setattr(disbursements_module, "get_selcom_business_client", lambda: _BlockedProvider())

    super_admin_id = uuid.uuid4()
    make_super_admin(fake_client, super_admin_id)
    response = _approve(body["id"], super_admin_id)

    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "BLOCKED_IP_WHITELIST"
    # Reserved, and left reserved — this isn't a payout failure.
    assert _wallet_balance(fake_client, merchant_id) == Decimal("10000.00") - Decimal("4000.00")


def test_ambiguous_provider_result_needs_reconciliation(fake_client, monkeypatch):
    import app.services.disbursements as disbursements_module
    from app.services.selcom_business.schemas import SelcomBusinessResult

    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "10000.00")
    body = _request_withdrawal(merchant_id, admin_id, "4000.00")

    class _AmbiguousProvider:
        async def process_transaction(self, **kwargs):
            return SelcomBusinessResult(transaction_id="SEL-AMB-1", status="ambiguous")

    monkeypatch.setattr(disbursements_module, "get_selcom_business_client", lambda: _AmbiguousProvider())

    super_admin_id = uuid.uuid4()
    make_super_admin(fake_client, super_admin_id)
    response = _approve(body["id"], super_admin_id)

    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "NEEDS_RECONCILIATION"
    assert _wallet_balance(fake_client, merchant_id) == Decimal("10000.00") - Decimal("4000.00")


def test_processing_result_can_be_resolved_by_refresh_status(fake_client, monkeypatch):
    import app.services.disbursements as disbursements_module
    from app.services.selcom_business.schemas import SelcomBusinessResult

    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "10000.00")
    body = _request_withdrawal(merchant_id, admin_id, "4000.00")

    class _ProcessingThenSuccessProvider:
        async def process_transaction(self, **kwargs):
            return SelcomBusinessResult(transaction_id="SEL-PROC-1", status="processing")

        async def query_transaction(self, **kwargs):
            return SelcomBusinessResult(transaction_id="SEL-PROC-1", status="successful")

    monkeypatch.setattr(disbursements_module, "get_selcom_business_client", lambda: _ProcessingThenSuccessProvider())

    super_admin_id = uuid.uuid4()
    make_super_admin(fake_client, super_admin_id)
    approved = _approve(body["id"], super_admin_id).json()["data"]
    assert approved["status"] == "PROCESSING"

    refreshed = client.post(
        f"/v1/admin/withdrawals/{body['id']}/refresh-status", headers=auth_headers(super_admin_id)
    )
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["data"]["status"] == "SUCCESS"


def test_reconcile_pending_resolves_stuck_withdrawals(fake_client, monkeypatch):
    import app.services.disbursements as disbursements_module
    from app.services.selcom_business.schemas import SelcomBusinessResult

    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "10000.00")
    body = _request_withdrawal(merchant_id, admin_id, "4000.00")

    class _ProcessingThenSuccessProvider:
        async def process_transaction(self, **kwargs):
            return SelcomBusinessResult(transaction_id="SEL-PROC-2", status="processing")

        async def query_transaction(self, **kwargs):
            return SelcomBusinessResult(transaction_id="SEL-PROC-2", status="successful")

    monkeypatch.setattr(disbursements_module, "get_selcom_business_client", lambda: _ProcessingThenSuccessProvider())

    super_admin_id = uuid.uuid4()
    make_super_admin(fake_client, super_admin_id)
    _approve(body["id"], super_admin_id)

    response = client.post("/v1/admin/withdrawals/reconcile-pending", headers=auth_headers(super_admin_id))

    assert response.status_code == 200, response.text
    summary = response.json()["data"]
    assert summary["checked"] == 1
    assert summary["resolved"] == 1


# --- reject --------------------------------------------------------------------


def test_reject_requires_reason(fake_client):
    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "10000.00")
    body = _request_withdrawal(merchant_id, admin_id, "1000.00")

    super_admin_id = uuid.uuid4()
    make_super_admin(fake_client, super_admin_id)

    response = client.post(
        f"/v1/admin/withdrawals/{body['id']}/reject", headers=auth_headers(super_admin_id), json={}
    )
    assert response.status_code == 422


def test_reject_sets_rejected_status_and_releases_nothing(fake_client):
    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "10000000.00")
    body = _request_withdrawal(merchant_id, admin_id, "5000000.00")

    super_admin_id = uuid.uuid4()
    make_super_admin(fake_client, super_admin_id)
    response = _reject(body["id"], super_admin_id, reason="Duplicate request")

    assert response.status_code == 200, response.text
    rejected = response.json()["data"]
    assert rejected["status"] == "REJECTED"
    assert rejected["rejection_reason"] == "Duplicate request"
    assert rejected["rejected_by"] == str(super_admin_id)
    # Never reserved, so there's nothing to give back.
    assert _wallet_balance(fake_client, merchant_id) == Decimal("10000000.00")

    # Regression: reject_disbursement previously never called notify_merchant
    # at all (unlike the failed/info-requested paths) — the merchant only
    # ever saw a bare "Rejected" status with no visible reason. Note:
    # "withdrawal_rejected" must also be a valid notification_type per the
    # real notifications table's CHECK constraint
    # (supabase/migrations/20260822043100_notifications_withdrawal_rejected_type.sql)
    # — FakeSupabaseClient doesn't enforce that constraint, so this
    # assertion alone can't catch a real mismatch there; it only confirms
    # the notification is sent with the intended type/content.
    notifications = fake_client.table("notifications")._table.rows
    rejection_notifications = [n for n in notifications if n["notification_type"] == "withdrawal_rejected"]
    assert len(rejection_notifications) == 1
    assert rejection_notifications[0]["body"] == "Duplicate request"


def test_approve_rejects_already_completed_withdrawal(fake_client):
    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "10000.00")
    body = _request_withdrawal(merchant_id, admin_id, "1000.00")

    super_admin_id = uuid.uuid4()
    make_super_admin(fake_client, super_admin_id)
    _approve(body["id"], super_admin_id)

    response = _approve(body["id"], super_admin_id)
    assert response.status_code == 409


# --- request-info ---------------------------------------------------------------


def test_request_info_sets_info_requested(fake_client):
    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "10000.00")
    body = _request_withdrawal(merchant_id, admin_id, "1000.00")

    super_admin_id = uuid.uuid4()
    make_super_admin(fake_client, super_admin_id)

    response = client.post(
        f"/v1/admin/withdrawals/{body['id']}/request-info",
        headers=auth_headers(super_admin_id),
        json={"message": "Please confirm the recipient's full legal name.", "requested_documents": ["National ID"]},
    )

    assert response.status_code == 200, response.text
    updated = response.json()["data"]
    assert updated["status"] == "INFO_REQUESTED"
    assert updated["admin_status_reason"] == "Please confirm the recipient's full legal name."
    notifications = fake_client.table("notifications")._table.rows
    assert any(n["notification_type"] == "withdrawal_info_requested" for n in notifications)


def test_reject_allowed_after_info_requested(fake_client):
    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "10000.00")
    body = _request_withdrawal(merchant_id, admin_id, "1000.00")

    super_admin_id = uuid.uuid4()
    make_super_admin(fake_client, super_admin_id)
    client.post(
        f"/v1/admin/withdrawals/{body['id']}/request-info",
        headers=auth_headers(super_admin_id),
        json={"message": "Need more info", "requested_documents": []},
    )

    response = _reject(body["id"], super_admin_id)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "REJECTED"


# --- role enforcement ------------------------------------------------------------


@pytest.mark.parametrize(
    "make_request",
    [
        lambda wid, uid: _approve(wid, uid),
        lambda wid, uid: _reject(wid, uid),
        lambda wid, uid: client.post(
            f"/v1/admin/withdrawals/{wid}/request-info", headers=auth_headers(uid), json={"message": "x"}
        ),
        lambda wid, uid: client.post(f"/v1/admin/withdrawals/{wid}/refresh-status", headers=auth_headers(uid)),
    ],
)
def test_non_super_admin_cannot_act_on_withdrawals(fake_client, make_request):
    merchant_id, admin_id = _merchant_and_admin(fake_client)
    _fund_wallet(fake_client, merchant_id, "10000.00")
    body = _request_withdrawal(merchant_id, admin_id, "1000.00")

    non_admin_id = uuid.uuid4()
    response = make_request(body["id"], non_admin_id)
    assert response.status_code == 403


def test_non_super_admin_cannot_reconcile_pending(fake_client):
    non_admin_id = uuid.uuid4()
    response = client.post("/v1/admin/withdrawals/reconcile-pending", headers=auth_headers(non_admin_id))
    assert response.status_code == 403
