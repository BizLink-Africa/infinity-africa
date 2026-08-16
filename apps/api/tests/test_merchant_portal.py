"""Self-service /v1/merchant/* API: own-merchant resolution, role
enforcement, the overview aggregation, withdrawals dispatch, and
transaction-by-reference lookup — end to end against the in-memory
FakeSupabaseClient (see tests/fakes.py), same pattern as test_routers.py.
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


def _merchant_and_member(fake_client, role: str = "MERCHANT_ADMIN", **merchant_overrides):
    merchant = create_merchant(fake_client, **merchant_overrides)
    merchant_id = uuid.UUID(merchant["id"])
    user_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, user_id, role)
    return merchant_id, user_id


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


def _idem() -> str:
    return uuid.uuid4().hex


# --- Own-merchant resolution -------------------------------------------------


def test_me_404s_with_no_membership(fake_client):
    user_id = uuid.uuid4()
    response = client.get("/v1/merchant/me", headers=auth_headers(user_id))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_me_404s_with_inactive_membership(fake_client):
    merchant = create_merchant(fake_client)
    user_id = uuid.uuid4()
    fake_client.seed(
        "merchant_users",
        {"merchant_id": merchant["id"], "user_id": str(user_id), "role": "MERCHANT_ADMIN", "status": "invited"},
    )
    response = client.get("/v1/merchant/me", headers=auth_headers(user_id))
    assert response.status_code == 404


def test_me_returns_own_merchant_for_valid_membership(fake_client):
    merchant_id, user_id = _merchant_and_member(fake_client)
    response = client.get("/v1/merchant/me", headers=auth_headers(user_id))
    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(merchant_id)


def test_super_admin_has_no_own_merchant(fake_client):
    """/v1/merchant/* is a merchant-dashboard-only surface — a super admin
    with no merchant_users row of their own gets the same 404 anyone else
    without a membership would, no bypass."""
    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)
    response = client.get("/v1/merchant/me", headers=auth_headers(admin_id))
    assert response.status_code == 404


# --- Role enforcement ---------------------------------------------------------


def test_staff_can_create_payment_link(fake_client):
    merchant_id, user_id = _merchant_and_member(fake_client, role="MERCHANT_STAFF")
    response = client.post(
        "/v1/merchant/payment-links",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={"amount": "1000", "currency": "TZS"},
    )
    assert response.status_code == 201
    assert response.json()["data"]["merchant_id"] == str(merchant_id)


def test_developer_cannot_create_payment_link(fake_client):
    _merchant_id, user_id = _merchant_and_member(fake_client, role="DEVELOPER")
    response = client.post(
        "/v1/merchant/payment-links",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={"amount": "1000", "currency": "TZS"},
    )
    assert response.status_code == 403


# --- Payment link extended fields / edit route -------------------------------


def test_create_payment_link_accepts_new_fields(fake_client):
    _merchant_id, user_id = _merchant_and_member(fake_client)
    response = client.post(
        "/v1/merchant/payment-links",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={
            "amount": "1000",
            "currency": "TZS",
            "customer_email": "grace@example.com",
            "merchant_reference": "ORDER-4821",
            "success_redirect_url": "https://merchant.example.com/thank-you",
            "failure_redirect_url": "https://merchant.example.com/try-again",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()["data"]
    assert body["customer_email"] == "grace@example.com"
    assert body["merchant_reference"] == "ORDER-4821"
    assert body["success_redirect_url"] == "https://merchant.example.com/thank-you"
    assert body["failure_redirect_url"] == "https://merchant.example.com/try-again"
    assert body["paid_at"] is None
    assert body["attempt_count"] == 0


def test_update_payment_link_while_active_succeeds(fake_client):
    _merchant_id, user_id = _merchant_and_member(fake_client)
    link = client.post(
        "/v1/merchant/payment-links",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={"amount": "1000", "currency": "TZS", "description": "Original"},
    ).json()["data"]

    response = client.patch(
        f"/v1/merchant/payment-links/{link['id']}",
        headers=auth_headers(user_id),
        json={"description": "Updated description", "amount": "2000"},
    )

    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["description"] == "Updated description"
    assert Decimal(body["amount"]) == Decimal(2000)


def test_update_payment_link_rejects_non_active(fake_client):
    _merchant_id, user_id = _merchant_and_member(fake_client)
    link = client.post(
        "/v1/merchant/payment-links",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={"amount": "1000", "currency": "TZS"},
    ).json()["data"]
    client.patch(f"/v1/merchant/payment-links/{link['id']}/cancel", headers=auth_headers(user_id))

    response = client.patch(
        f"/v1/merchant/payment-links/{link['id']}",
        headers=auth_headers(user_id),
        json={"description": "Should not apply"},
    )

    assert response.status_code == 409


def test_update_payment_link_from_another_merchant_not_found(fake_client):
    _merchant_id, user_id = _merchant_and_member(fake_client)
    link = client.post(
        "/v1/merchant/payment-links",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={"amount": "1000", "currency": "TZS"},
    ).json()["data"]

    _other_merchant_id, other_user_id = _merchant_and_member(fake_client, contact_email="other@example.com")
    response = client.patch(
        f"/v1/merchant/payment-links/{link['id']}",
        headers=auth_headers(other_user_id),
        json={"description": "Not yours"},
    )

    assert response.status_code == 404


def test_attempt_count_reflects_collections_against_the_link(fake_client):
    merchant_id, user_id = _merchant_and_member(fake_client)
    link = client.post(
        "/v1/merchant/payment-links",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={"amount": "1000", "currency": "TZS"},
    ).json()["data"]

    fake_client.seed(
        "collections",
        {
            "merchant_id": str(merchant_id),
            "payment_link_id": link["id"],
            "method": "STK_PUSH",
            "amount": "1000.00",
            "currency": "TZS",
            "status": "failed",
        },
    )
    fake_client.seed(
        "collections",
        {
            "merchant_id": str(merchant_id),
            "payment_link_id": link["id"],
            "method": "STK_PUSH",
            "amount": "1000.00",
            "currency": "TZS",
            "status": "successful",
        },
    )

    get_response = client.get(f"/v1/merchant/payment-links/{link['id']}", headers=auth_headers(user_id))
    assert get_response.json()["data"]["attempt_count"] == 2

    list_response = client.get("/v1/merchant/payment-links", headers=auth_headers(user_id))
    listed = next(row for row in list_response.json()["data"] if row["id"] == link["id"])
    assert listed["attempt_count"] == 2


def test_staff_cannot_create_withdrawal(fake_client):
    """The one deliberate tightening vs. the existing /v1/disbursements/*
    routes, which also allow MERCHANT_STAFF."""
    merchant_id, user_id = _merchant_and_member(fake_client, role="MERCHANT_STAFF")
    _fund_wallet(fake_client, merchant_id, "500000")
    response = client.post(
        "/v1/merchant/withdrawals",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={
            "method": "MOBILE_MONEY",
            "amount": "10000",
            "destination_name": "Jane",
            "destination_phone": "+255700000000",
        },
    )
    assert response.status_code == 403


def test_staff_can_view_withdrawals(fake_client):
    _merchant_id, user_id = _merchant_and_member(fake_client, role="MERCHANT_STAFF")
    response = client.get("/v1/merchant/withdrawals", headers=auth_headers(user_id))
    assert response.status_code == 200


# --- Self-service collections (/v1/merchant/collections/*) -----------------


def test_staff_can_initiate_stk_push_collection(fake_client):
    merchant_id, user_id = _merchant_and_member(fake_client, role="MERCHANT_STAFF")
    response = client.post(
        "/v1/merchant/collections/stk-push",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={"amount": "1000.00", "customer_phone": "+255700000000"},
    )
    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["merchant_id"] == str(merchant_id)
    assert data["status"] == "processing"
    assert data["transaction_reference"]
    assert data["message"]


def test_self_service_dynamic_qr_returns_qr_payload(fake_client):
    _merchant_id, user_id = _merchant_and_member(fake_client, role="MERCHANT_ADMIN")
    response = client.post(
        "/v1/merchant/collections/dynamic-qr",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={"amount": "2500.00"},
    )
    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["qr_payload"]
    assert data["expires_at"] == data["qr_expires_at"]


def test_self_service_collection_rejects_expired_payment_link(fake_client):
    """Regression test: /v1/merchant/collections/* previously skipped
    payment_link_id validation entirely (unlike the flat /v1/collections/*
    router), so a merchant's own dashboard/API-key flow could silently
    initiate a collection against an already-expired payment link."""
    _merchant_id, user_id = _merchant_and_member(fake_client, role="MERCHANT_ADMIN")
    link = client.post(
        "/v1/merchant/payment-links",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={"amount": "1000", "currency": "TZS"},
    ).json()["data"]
    fake_client.table("payment_links")._table.rows[0]["status"] = "EXPIRED"
    assert fake_client.table("payment_links")._table.rows[0]["id"] == link["id"]

    response = client.post(
        "/v1/merchant/collections/stk-push",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={"amount": "1000.00", "customer_phone": "+255700000000", "payment_link_id": link["id"]},
    )

    assert response.status_code == 409
    assert len(fake_client.table("collections")._table.rows) == 0


def test_developer_can_create_api_key(fake_client):
    _merchant_id, user_id = _merchant_and_member(fake_client, role="DEVELOPER")
    response = client.post(
        "/v1/merchant/api-keys",
        headers=auth_headers(user_id),
        json={"name": "Dev key", "scopes": ["collections:write", "collections:read"]},
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert "plaintext_key" in body
    assert body["plaintext_key"].startswith("inf_sandbox_")
    assert body["scopes"] == ["collections:write", "collections:read"]


def test_create_api_key_rejects_unknown_scope(fake_client):
    _merchant_id, user_id = _merchant_and_member(fake_client, role="DEVELOPER")
    response = client.post(
        "/v1/merchant/api-keys",
        headers=auth_headers(user_id),
        json={"name": "Bad key", "scopes": ["not_a_real_scope"]},
    )
    assert response.status_code == 422


def test_list_api_keys_never_includes_plaintext_or_hash(fake_client):
    _merchant_id, user_id = _merchant_and_member(fake_client, role="DEVELOPER")
    client.post(
        "/v1/merchant/api-keys",
        headers=auth_headers(user_id),
        json={"name": "Dev key", "scopes": ["collections:write"]},
    )

    response = client.get("/v1/merchant/api-keys", headers=auth_headers(user_id))

    assert response.status_code == 200
    key = response.json()["data"][0]
    assert "plaintext_key" not in key
    assert "hashed_key" not in key
    assert key["scopes"] == ["collections:write"]


def test_revoke_api_key_keeps_scopes_and_marks_revoked(fake_client):
    _merchant_id, user_id = _merchant_and_member(fake_client, role="DEVELOPER")
    created = client.post(
        "/v1/merchant/api-keys",
        headers=auth_headers(user_id),
        json={"name": "Dev key", "scopes": ["invoices:read"]},
    ).json()["data"]

    response = client.patch(
        f"/v1/merchant/api-keys/{created['id']}/revoke", headers=auth_headers(user_id)
    )

    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["status"] == "revoked"
    assert body["scopes"] == ["invoices:read"]


def test_staff_cannot_manage_api_keys(fake_client):
    _merchant_id, user_id = _merchant_and_member(fake_client, role="MERCHANT_STAFF")
    response = client.post(
        "/v1/merchant/api-keys", headers=auth_headers(user_id), json={"name": "Staff key"}
    )
    assert response.status_code == 403


# --- Invoices: create -> send ------------------------------------------------


def test_create_then_send_invoice(fake_client):
    _merchant_id, user_id = _merchant_and_member(fake_client)
    create_response = client.post(
        "/v1/merchant/invoices",
        headers=auth_headers(user_id),
        json={
            "due_date": "2026-12-01",
            "items": [{"description": "Consulting", "quantity": "1", "unit_price": "5000"}],
        },
    )
    assert create_response.status_code == 201
    invoice = create_response.json()["data"]
    assert invoice["status"] == "DRAFT"

    send_response = client.post(
        f"/v1/merchant/invoices/{invoice['id']}/send", headers=auth_headers(user_id)
    )
    assert send_response.status_code == 200
    assert send_response.json()["data"]["status"] == "SENT"


# --- Overview aggregation ------------------------------------------------------


def test_overview_aggregates_all_fields(fake_client):
    merchant_id, user_id = _merchant_and_member(fake_client)

    # Two successful collections: 10,000 gross/300 fee, and 5,000 gross/150 fee.
    fake_client.seed(
        "transactions",
        {
            "merchant_id": str(merchant_id),
            "reference": "TXN-1",
            "type": "collection",
            "method": "USSD_PUSH",
            "gross_amount": "10000",
            "fee_amount": "300",
            "net_amount": "9700",
            "currency": "TZS",
            "status": "successful",
        },
    )
    fake_client.seed(
        "transactions",
        {
            "merchant_id": str(merchant_id),
            "reference": "TXN-2",
            "type": "collection",
            "method": "STK_PUSH",
            "gross_amount": "5000",
            "fee_amount": "150",
            "net_amount": "4850",
            "currency": "TZS",
            "status": "successful",
        },
    )
    # One pending, one processing transaction (of any type).
    fake_client.seed(
        "transactions",
        {
            "merchant_id": str(merchant_id),
            "reference": "TXN-3",
            "type": "collection",
            "method": "STK_PUSH",
            "gross_amount": "2000",
            "fee_amount": "0",
            "net_amount": "2000",
            "currency": "TZS",
            "status": "pending",
        },
    )
    fake_client.seed(
        "transactions",
        {
            "merchant_id": str(merchant_id),
            "reference": "TXN-4",
            "type": "disbursement",
            "method": "MOBILE_MONEY",
            "gross_amount": "1000",
            "fee_amount": "0",
            "net_amount": "1000",
            "currency": "TZS",
            "status": "processing",
        },
    )
    # One successful disbursement.
    fake_client.seed(
        "transactions",
        {
            "merchant_id": str(merchant_id),
            "reference": "TXN-5",
            "type": "disbursement",
            "method": "SELCOM_PESA",
            "gross_amount": "3000",
            "fee_amount": "0",
            "net_amount": "3000",
            "currency": "TZS",
            "status": "successful",
        },
    )

    # Payment links: one active-not-expired, one active-but-expired, one cancelled.
    fake_client.seed(
        "payment_links",
        {
            "merchant_id": str(merchant_id),
            "amount": "1000",
            "currency": "TZS",
            "allowed_payment_methods": ["USSD_PUSH"],
            "public_slug": "slug-active",
            "status": "ACTIVE",
            "expires_at": None,
        },
    )
    fake_client.seed(
        "payment_links",
        {
            "merchant_id": str(merchant_id),
            "amount": "1000",
            "currency": "TZS",
            "allowed_payment_methods": ["USSD_PUSH"],
            "public_slug": "slug-expired",
            "status": "ACTIVE",
            "expires_at": "2020-01-01T00:00:00+00:00",
        },
    )
    fake_client.seed(
        "payment_links",
        {
            "merchant_id": str(merchant_id),
            "amount": "1000",
            "currency": "TZS",
            "allowed_payment_methods": ["USSD_PUSH"],
            "public_slug": "slug-cancelled",
            "status": "CANCELLED",
            "expires_at": None,
        },
    )

    # Invoices: one SENT (unpaid), one PAID, one DRAFT.
    fake_client.seed(
        "invoices",
        {
            "merchant_id": str(merchant_id),
            "invoice_number": "INV-1",
            "due_date": "2026-12-01",
            "currency": "TZS",
            "subtotal": "1000",
            "tax_amount": "0",
            "discount_amount": "0",
            "total_amount": "1000",
            "amount_paid": "0",
            "status": "SENT",
        },
    )
    fake_client.seed(
        "invoices",
        {
            "merchant_id": str(merchant_id),
            "invoice_number": "INV-2",
            "due_date": "2026-12-01",
            "currency": "TZS",
            "subtotal": "1000",
            "tax_amount": "0",
            "discount_amount": "0",
            "total_amount": "1000",
            "amount_paid": "1000",
            "status": "PAID",
        },
    )
    fake_client.seed(
        "invoices",
        {
            "merchant_id": str(merchant_id),
            "invoice_number": "INV-3",
            "due_date": "2026-12-01",
            "currency": "TZS",
            "subtotal": "1000",
            "tax_amount": "0",
            "discount_amount": "0",
            "total_amount": "1000",
            "amount_paid": "0",
            "status": "DRAFT",
        },
    )

    _fund_wallet(fake_client, merchant_id, "42000")

    response = client.get("/v1/merchant/overview", headers=auth_headers(user_id))
    assert response.status_code == 200
    data = response.json()["data"]

    assert data["merchant"]["id"] == str(merchant_id)
    assert Decimal(data["total_collections"]) == Decimal(15000)
    assert Decimal(data["available_balance"]) == Decimal(42000)
    assert data["pending_transactions"] == 2  # TXN-3 (pending) + TXN-4 (processing)
    assert data["successful_withdrawals"] == 1  # TXN-5
    assert data["active_payment_links"] == 1  # only slug-active
    assert data["unpaid_invoices"] == 1  # only INV-1
    assert Decimal(data["total_fees_charged"]) == Decimal(450)


def test_overview_404s_with_no_membership(fake_client):
    user_id = uuid.uuid4()
    response = client.get("/v1/merchant/overview", headers=auth_headers(user_id))
    assert response.status_code == 404


# --- Withdrawals dispatch -------------------------------------------------


@pytest.mark.parametrize(
    ("method", "body_extra"),
    [
        ("SELCOM_PESA", {"destination_phone": "+255700000001"}),
        ("MOBILE_MONEY", {"destination_phone": "+255700000002"}),
        ("BANK_ACCOUNT", {"bank_name": "CRDB", "bank_account_number": "1234567890", "bank_account_name": "Jane Doe"}),
    ],
)
def test_withdrawal_dispatches_to_correct_method(fake_client, method, body_extra):
    merchant_id, user_id = _merchant_and_member(fake_client)
    _fund_wallet(fake_client, merchant_id, "100000")

    response = client.post(
        "/v1/merchant/withdrawals",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={"method": method, "amount": "10000", "destination_name": "Jane", **body_extra},
    )
    assert response.status_code == 202
    body = response.json()["data"]
    assert body["method"] == method
    assert body["merchant_id"] == str(merchant_id)


def test_withdrawal_insufficient_balance_returns_409(fake_client):
    merchant_id, user_id = _merchant_and_member(fake_client)
    _fund_wallet(fake_client, merchant_id, "1000")

    response = client.post(
        "/v1/merchant/withdrawals",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={
            "method": "MOBILE_MONEY",
            "amount": "50000",
            "destination_name": "Jane",
            "destination_phone": "+255700000003",
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_balance"


def test_withdrawal_bank_account_requires_bank_fields(fake_client):
    _merchant_id, user_id = _merchant_and_member(fake_client)
    response = client.post(
        "/v1/merchant/withdrawals",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={"method": "BANK_ACCOUNT", "amount": "10000", "destination_name": "Jane"},
    )
    assert response.status_code == 422


def test_withdrawal_mobile_money_accepts_optional_network(fake_client):
    merchant_id, user_id = _merchant_and_member(fake_client)
    _fund_wallet(fake_client, merchant_id, "100000")

    response = client.post(
        "/v1/merchant/withdrawals",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={
            "method": "MOBILE_MONEY",
            "amount": "10000",
            "destination_name": "Jane",
            "destination_phone": "+255700000003",
            "network": "TIGO_PESA",
        },
    )

    assert response.status_code == 202, response.text
    body = response.json()["data"]
    assert body["status"] == "SUCCESS"
    assert body["transaction_reference"]
    assert body["net_amount"] is not None


# --- Transactions by reference -----------------------------------------------


def test_get_transaction_by_reference_found(fake_client):
    merchant_id, user_id = _merchant_and_member(fake_client)
    fake_client.seed(
        "transactions",
        {
            "merchant_id": str(merchant_id),
            "reference": "TXN-FINDME",
            "type": "collection",
            "method": "USSD_PUSH",
            "gross_amount": "1000",
            "fee_amount": "0",
            "net_amount": "1000",
            "currency": "TZS",
            "status": "successful",
            "metadata": {},
        },
    )
    response = client.get("/v1/merchant/transactions/TXN-FINDME", headers=auth_headers(user_id))
    assert response.status_code == 200
    assert response.json()["data"]["reference"] == "TXN-FINDME"


def test_get_transaction_by_reference_not_found(fake_client):
    _merchant_id, user_id = _merchant_and_member(fake_client)
    response = client.get("/v1/merchant/transactions/TXN-NOPE", headers=auth_headers(user_id))
    assert response.status_code == 404


def test_get_transaction_by_reference_cross_tenant_not_leaked(fake_client):
    """Another merchant's transaction, matched by reference alone, must not
    be visible to a caller from a different merchant."""
    other_merchant_id, _other_user = _merchant_and_member(fake_client)
    fake_client.seed(
        "transactions",
        {
            "merchant_id": str(other_merchant_id),
            "reference": "TXN-SHARED-REF",
            "type": "collection",
            "method": "USSD_PUSH",
            "gross_amount": "1000",
            "fee_amount": "0",
            "net_amount": "1000",
            "currency": "TZS",
            "status": "successful",
        },
    )
    _my_merchant_id, my_user_id = _merchant_and_member(fake_client)
    response = client.get("/v1/merchant/transactions/TXN-SHARED-REF", headers=auth_headers(my_user_id))
    assert response.status_code == 404
