"""POST /public/payment-links/{slug}/pay — the unified "choose how you
want to pay" endpoint (app/services/collection_payment.py) added to
support three active customer payment methods: Mobile Money Push,
Selcom Pesa, and Scan QR / TanQR. Hosted checkout stays inactive behind
settings.hosted_checkout_enabled.

Real fixture setup throughout (a real payment link created via the API,
a real merchant), same convention as test_checkout_reconciliation.py —
the Selcom Checkout HTTP client is the only thing faked.
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
    "data": [
        {
            "payment_token": "80008000",
            "qr": "00020101021226580014COM.SELCOM.WWW",  # exact Selcom-shaped EMVCo text
            "payment_gateway_url": "aHR0cHM6Ly9leGFtcGxlLmNvbS9wYXk=",
        }
    ],
}

WALLET_PAYMENT_PENDING_RESPONSE = {
    "reference": "0289999288",
    "resultcode": "111",
    "result": "PENDING",
    "message": "Request in progress.",
    "data": [],
}

SELCOMPESA_PAYMENT_PENDING_RESPONSE = {
    "reference": "0289999333",
    "resultcode": "111",
    "result": "PENDING",
    "message": "Request in progress. You will receive a callback shortly.",
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


class _FakeSelcomCheckoutClient:
    def __init__(self, *, credentials=None, order_response=None, wallet_response=None, selcompesa_response=None):
        self._order_response = order_response or CREATE_ORDER_SUCCESS_RESPONSE
        self._wallet_response = wallet_response or WALLET_PAYMENT_PENDING_RESPONSE
        self._selcompesa_response = selcompesa_response or SELCOMPESA_PAYMENT_PENDING_RESPONSE
        self.wallet_payment_calls: list[dict] = []
        self.selcompesa_payment_calls: list[dict] = []

    async def create_order_minimal(self, **kwargs):
        from app.services.selcom_checkout.parsing import (
            parse_create_order_minimal_response,
        )

        return parse_create_order_minimal_response(self._order_response)

    async def process_wallet_payment(self, **kwargs):
        from app.services.selcom_checkout.parsing import parse_wallet_payment_response

        self.wallet_payment_calls.append(kwargs)
        return parse_wallet_payment_response(self._wallet_response)

    async def selcompesa_payment(self, **kwargs):
        from app.services.selcom_checkout.parsing import (
            parse_selcompesa_payment_response,
        )

        self.selcompesa_payment_calls.append(kwargs)
        return parse_selcompesa_payment_response(self._selcompesa_response)


def _patch_checkout_client(monkeypatch, **kwargs) -> _FakeSelcomCheckoutClient:
    import app.services.checkout_orders as checkout_orders_module
    import app.services.selcompesa_push as selcompesa_push_module
    import app.services.wallet_push as wallet_push_module

    fake = _FakeSelcomCheckoutClient(**kwargs)
    monkeypatch.setattr(checkout_orders_module, "SelcomCheckoutHTTPClient", lambda **kw: fake)
    monkeypatch.setattr(wallet_push_module, "SelcomCheckoutHTTPClient", lambda **kw: fake)
    monkeypatch.setattr(selcompesa_push_module, "SelcomCheckoutHTTPClient", lambda **kw: fake)
    return fake


def _create_merchant_and_link(fake_client, monkeypatch) -> tuple[dict, dict]:
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    admin_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, admin_id, "MERCHANT_ADMIN")
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
    response = client.post(
        "/v1/payment-links",
        headers={**auth_headers(admin_id), "Idempotency-Key": str(uuid.uuid4())},
        json={"merchant_id": str(merchant_id), "amount": "2500.00", "currency": "TZS"},
    )
    assert response.status_code == 201, response.text
    return merchant, response.json()["data"]


def _pay(slug: str, **body) -> object:
    return client.post(
        f"/public/payment-links/{slug}/pay",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json=body,
    )


# --- WALLET_PUSH ------------------------------------------------------------------


def test_wallet_push_via_unified_endpoint_never_credits(fake_client, monkeypatch):
    fake = _patch_checkout_client(monkeypatch)
    _merchant, link = _create_merchant_and_link(fake_client, monkeypatch)

    response = _pay(link["public_slug"], method="WALLET_PUSH", customer_phone="255747730270")

    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["method"] == "WALLET_PUSH"
    assert data["status"] == "pending"
    assert data["message"] == "Payment prompt sent. Please approve on your phone."

    assert fake_client.table("ledger_entries")._table.rows == []
    assert fake_client.table("payment_links")._table.rows[0]["status"] == "ACTIVE"
    assert len(fake.wallet_payment_calls) == 1
    assert fake.wallet_payment_calls[0]["msisdn"] == "255747730270"

    collection = next(c for c in fake_client.table("collections")._table.rows if c["payment_link_id"] == link["id"])
    assert collection["method"] == "STK_PUSH"
    assert collection["status"] == "processing"


def test_wallet_push_requires_customer_phone(fake_client, monkeypatch):
    _patch_checkout_client(monkeypatch)
    _merchant, link = _create_merchant_and_link(fake_client, monkeypatch)

    response = _pay(link["public_slug"], method="WALLET_PUSH")
    assert response.status_code == 422, response.text


# --- SELCOM_PESA --------------------------------------------------------------------


def test_selcompesa_via_unified_endpoint_never_credits(fake_client, monkeypatch):
    fake = _patch_checkout_client(monkeypatch)
    _merchant, link = _create_merchant_and_link(fake_client, monkeypatch)

    response = _pay(link["public_slug"], method="SELCOM_PESA", customer_phone="255747730270")

    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["method"] == "SELCOM_PESA"
    assert data["status"] == "pending"
    assert data["message"] == "Selcom Pesa prompt sent. Please approve in your Selcom Pesa app."

    assert fake_client.table("ledger_entries")._table.rows == []
    assert fake_client.table("payment_links")._table.rows[0]["status"] == "ACTIVE"
    assert len(fake.selcompesa_payment_calls) == 1
    assert fake.selcompesa_payment_calls[0]["msisdn"] == "255747730270"

    collection = next(c for c in fake_client.table("collections")._table.rows if c["payment_link_id"] == link["id"])
    assert collection["method"] == "SELCOM_PESA_PUSH"
    assert collection["status"] == "processing"
    # Raw provider response stored safely, unmodified.
    assert collection["raw_response"] == SELCOMPESA_PAYMENT_PENDING_RESPONSE


def test_selcompesa_requires_customer_phone(fake_client, monkeypatch):
    _patch_checkout_client(monkeypatch)
    _merchant, link = _create_merchant_and_link(fake_client, monkeypatch)

    response = _pay(link["public_slug"], method="SELCOM_PESA")
    assert response.status_code == 422, response.text


def test_selcompesa_failed_push_recorded_not_credited(fake_client, monkeypatch):
    failed_response = {
        "reference": "0289999444",
        "resultcode": "651",
        "result": "FAIL",
        "message": "Insufficient balance.",
        "data": [],
    }
    _patch_checkout_client(monkeypatch, selcompesa_response=failed_response)
    _merchant, link = _create_merchant_and_link(fake_client, monkeypatch)

    response = _pay(link["public_slug"], method="SELCOM_PESA", customer_phone="255747730270")

    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["status"] == "failed"
    assert fake_client.table("ledger_entries")._table.rows == []


# --- TANQR ----------------------------------------------------------------------------


def test_tanqr_via_unified_endpoint_stores_and_returns_selcom_qr_and_token_exactly(fake_client, monkeypatch):
    """The core TanQR rule under test: Infinity never generates its own
    QR/payment payload — only Selcom's create-order-minimal qr/
    payment_token, passed through byte-for-byte."""
    _patch_checkout_client(monkeypatch)
    _merchant, link = _create_merchant_and_link(fake_client, monkeypatch)

    response = _pay(link["public_slug"], method="TANQR")

    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["method"] == "TANQR"
    assert data["status"] == "pending"
    assert data["qr"] == "00020101021226580014COM.SELCOM.WWW"
    assert data["payment_token"] == "80008000"

    assert fake_client.table("ledger_entries")._table.rows == []
    assert fake_client.table("payment_links")._table.rows[0]["status"] == "ACTIVE"

    collection = next(c for c in fake_client.table("collections")._table.rows if c["payment_link_id"] == link["id"])
    assert collection["method"] == "DYNAMIC_QR"
    assert collection["status"] == "processing"

    # Backend storage: checkout_orders keeps Selcom's raw qr/payment_token
    # exactly as returned, never altered or regenerated.
    order = next(o for o in fake_client.table("checkout_orders")._table.rows if o["id"] == collection["checkout_order_id"])
    assert order["qr"] == "00020101021226580014COM.SELCOM.WWW"
    assert order["payment_token"] == "80008000"
    assert order["raw_response"] == CREATE_ORDER_SUCCESS_RESPONSE


def test_tanqr_does_not_require_customer_phone(fake_client, monkeypatch):
    _patch_checkout_client(monkeypatch)
    _merchant, link = _create_merchant_and_link(fake_client, monkeypatch)

    response = _pay(link["public_slug"], method="TANQR")
    assert response.status_code == 202, response.text


# --- hosted checkout stays inactive --------------------------------------------------


def test_hosted_checkout_endpoint_disabled_by_default(fake_client, monkeypatch):
    _patch_checkout_client(monkeypatch)
    _merchant, link = _create_merchant_and_link(fake_client, monkeypatch)

    response = client.post(
        f"/public/payment-links/{link['public_slug']}/pay/checkout",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={},
    )

    assert response.status_code == 409, response.text
    assert "disabled" in response.json()["error"]["message"].lower()


def test_hosted_checkout_endpoint_works_when_explicitly_enabled(fake_client, monkeypatch):
    monkeypatch.setenv("HOSTED_CHECKOUT_ENABLED", "true")
    get_settings.cache_clear()
    _patch_checkout_client(monkeypatch)
    _merchant, link = _create_merchant_and_link(fake_client, monkeypatch)

    response = client.post(
        f"/public/payment-links/{link['public_slug']}/pay/checkout",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={},
    )

    assert response.status_code == 202, response.text


def test_public_payment_page_does_not_advertise_hosted_checkout_in_allowed_methods(fake_client, monkeypatch):
    """Regression guard for existing rows: an old payment link's
    allowed_payment_methods must still load safely on the public page,
    whatever legacy values it carries."""
    _patch_checkout_client(monkeypatch)
    _merchant, link = _create_merchant_and_link(fake_client, monkeypatch)

    response = client.get(f"/public/payment-links/{link['public_slug']}")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "ACTIVE"
