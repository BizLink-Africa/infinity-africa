"""POST /v1/merchant/collections/wallet-push — Merchant Portal "Request
Collection" via wallet-push. TEMPORARY (2026-08-23): brought back
specifically because Selcom's hosted checkout is confirmed broken
account-side (see docs/selcom-checkout-collections.md, "Known issue"
section) — see app/services/wallet_push.py::execute_wallet_push_collection's
docstring. Exercises app/services/wallet_push.py end to end against the
in-memory FakeSupabaseClient. The real Selcom client is monkeypatched
out — this file never makes a network call.
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
    make_merchant_member,
)

client = TestClient(app)

CREATE_ORDER_SUCCESS_RESPONSE = {
    "reference": "S20690900000",
    "resultcode": "000",
    "result": "SUCCESS",
    "message": "Payment notification logged",
    "data": [{"payment_token": "TOKEN", "payment_gateway_url": "aHR0cHM6Ly9leGFtcGxlLmNvbQ==", "qr": "QR"}],
}

WALLET_PAYMENT_PENDING_RESPONSE = {
    "reference": "0289999288",
    "resultcode": "111",
    "result": "PENDING",
    "message": "Request in progress.",
    "data": [],
}

WALLET_PAYMENT_FAILED_RESPONSE = {
    "reference": "0289999299",
    "resultcode": "651",
    "result": "FAIL",
    "message": "Insufficient balance.",
    "data": [],
}


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("SELCOM_CHECKOUT_BASE_URL", "https://checkout.example.selcommobile.com")
    monkeypatch.setenv("SELCOM_CHECKOUT_API_KEY", "test-key")
    monkeypatch.setenv("SELCOM_CHECKOUT_API_SECRET", "test-secret")
    monkeypatch.setenv("SELCOM_CHECKOUT_VENDOR", "VENDORTEST")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _idem() -> str:
    return uuid.uuid4().hex


def _merchant_and_member(fake_client, role: str = "MERCHANT_ADMIN"):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    user_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, user_id, role)
    return merchant_id, user_id


class _FakeSelcomCheckoutClient:
    def __init__(self, *, credentials=None, wallet_payment_response: dict = WALLET_PAYMENT_PENDING_RESPONSE):
        self.wallet_payment_calls: list[dict] = []
        self._wallet_payment_response = wallet_payment_response

    async def create_order_minimal(self, **kwargs):
        from app.services.selcom_checkout.parsing import (
            parse_create_order_minimal_response,
        )

        return parse_create_order_minimal_response(CREATE_ORDER_SUCCESS_RESPONSE)

    async def process_wallet_payment(self, **kwargs):
        from app.services.selcom_checkout.parsing import parse_wallet_payment_response

        self.wallet_payment_calls.append(kwargs)
        return parse_wallet_payment_response(self._wallet_payment_response)


def _patch_checkout_client(monkeypatch, *, wallet_payment_response: dict = WALLET_PAYMENT_PENDING_RESPONSE):
    import app.services.checkout_orders as checkout_orders_module
    import app.services.wallet_push as wallet_push_module

    fake = _FakeSelcomCheckoutClient(wallet_payment_response=wallet_payment_response)
    monkeypatch.setattr(checkout_orders_module, "SelcomCheckoutHTTPClient", lambda **kwargs: fake)
    monkeypatch.setattr(wallet_push_module, "SelcomCheckoutHTTPClient", lambda **kwargs: fake)
    return fake


def _seed_wallet(fake_client, merchant_id):
    fake_client.seed(
        "ledger_accounts",
        {
            "merchant_id": str(merchant_id),
            "name": "Merchant Wallet (test)",
            "account_type": "liability",
            "purpose": "merchant_wallet",
            "currency": "TZS",
            "balance": "0",
        },
    )


def test_wallet_push_collection_accepts_request_without_channel(fake_client, monkeypatch):
    merchant_id, user_id = _merchant_and_member(fake_client)
    _patch_checkout_client(monkeypatch)

    response = client.post(
        "/v1/merchant/collections/wallet-push",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={"customer_name": "Grace", "customer_phone": "255747730270", "amount": "5000"},
    )

    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["method"] == "STK_PUSH"
    assert data["merchant_id"] == str(merchant_id)
    assert data["status"] == "processing"


def test_wallet_push_collection_requires_customer_phone(fake_client, monkeypatch):
    _merchant_id, user_id = _merchant_and_member(fake_client)
    _patch_checkout_client(monkeypatch)

    response = client.post(
        "/v1/merchant/collections/wallet-push",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={"amount": "5000"},
    )

    assert response.status_code == 422


def test_wallet_push_collection_sends_real_push_to_the_phone(fake_client, monkeypatch):
    _merchant_id, user_id = _merchant_and_member(fake_client)
    fake = _patch_checkout_client(monkeypatch)

    response = client.post(
        "/v1/merchant/collections/wallet-push",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={"customer_phone": "255747730270", "amount": "5000"},
    )

    assert response.status_code == 202, response.text
    assert len(fake.wallet_payment_calls) == 1
    assert fake.wallet_payment_calls[0]["msisdn"] == "255747730270"


def test_wallet_push_collection_creates_linked_transaction_for_later_resolution(fake_client, monkeypatch):
    merchant_id, user_id = _merchant_and_member(fake_client)
    _patch_checkout_client(monkeypatch)
    _seed_wallet(fake_client, merchant_id)

    response = client.post(
        "/v1/merchant/collections/wallet-push",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={"customer_phone": "255747730270", "amount": "5000"},
    )
    collection_id = response.json()["data"]["id"]

    collection_row = fake_client.table("collections")._table.rows[0]
    assert collection_row["id"] == collection_id
    assert any(t["collection_id"] == collection_id for t in fake_client.table("transactions")._table.rows)


def test_wallet_push_collection_failed_push_recorded_not_502(fake_client, monkeypatch):
    _merchant_id, user_id = _merchant_and_member(fake_client)
    _patch_checkout_client(monkeypatch, wallet_payment_response=WALLET_PAYMENT_FAILED_RESPONSE)

    response = client.post(
        "/v1/merchant/collections/wallet-push",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={"customer_phone": "255747730270", "amount": "5000"},
    )

    assert response.status_code == 202, response.text
    assert response.json()["data"]["status"] == "failed"


def test_wallet_push_collection_never_credits_synchronously(fake_client, monkeypatch):
    """Same rule as execute_wallet_push_for_payment_link: PENDING (the
    normal outcome) must never be treated as success — resolution only
    comes later via webhook/manual refresh."""
    merchant_id, user_id = _merchant_and_member(fake_client)
    _patch_checkout_client(monkeypatch)
    _seed_wallet(fake_client, merchant_id)

    response = client.post(
        "/v1/merchant/collections/wallet-push",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={"customer_phone": "255747730270", "amount": "5000"},
    )

    assert response.status_code == 202, response.text
    assert response.json()["data"]["status"] == "processing"
    assert fake_client.table("ledger_entries")._table.rows == []
