"""The external developer Collections API — POST/GET /v1/collections...
(app/routers/collections_api.py). Real fixture setup (a real merchant,
a real API key), same convention as test_unified_pay_endpoint.py — only
the Selcom Checkout HTTP client is faked.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from tests.factories import TEST_JWT_SECRET, create_merchant, make_api_key

client = TestClient(app)

CREATE_ORDER_SUCCESS_RESPONSE = {
    "reference": "S20690900000",
    "resultcode": "000",
    "result": "SUCCESS",
    "message": "Payment notification logged",
    "data": [
        {
            "payment_token": "80008000",
            "qr": "00020101021226580014COM.SELCOM.WWW",
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
    def __init__(self, *, credentials=None):
        pass

    async def create_order_minimal(self, **kwargs):
        from app.services.selcom_checkout.parsing import (
            parse_create_order_minimal_response,
        )

        return parse_create_order_minimal_response(CREATE_ORDER_SUCCESS_RESPONSE)

    async def process_wallet_payment(self, **kwargs):
        from app.services.selcom_checkout.parsing import parse_wallet_payment_response

        return parse_wallet_payment_response(WALLET_PAYMENT_PENDING_RESPONSE)

    async def selcompesa_payment(self, **kwargs):
        from app.services.selcom_checkout.parsing import (
            parse_selcompesa_payment_response,
        )

        return parse_selcompesa_payment_response(SELCOMPESA_PAYMENT_PENDING_RESPONSE)


def _patch_checkout_client(monkeypatch):
    import app.services.checkout_orders as checkout_orders_module
    import app.services.selcompesa_push as selcompesa_push_module
    import app.services.wallet_push as wallet_push_module

    fake = _FakeSelcomCheckoutClient()
    monkeypatch.setattr(checkout_orders_module, "SelcomCheckoutHTTPClient", lambda **kw: fake)
    monkeypatch.setattr(wallet_push_module, "SelcomCheckoutHTTPClient", lambda **kw: fake)
    monkeypatch.setattr(selcompesa_push_module, "SelcomCheckoutHTTPClient", lambda **kw: fake)
    return fake


def _merchant_and_key(fake_client, monkeypatch):
    _patch_checkout_client(monkeypatch)
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    raw_key, _ = make_api_key(fake_client, merchant_id)
    return merchant_id, raw_key


def _headers(raw_key: str) -> dict:
    return {"X-API-Key": raw_key, "Idempotency-Key": str(uuid.uuid4())}


# --- POST /v1/collections (Infinity Payment Page) --------------------------------------


def test_create_collection_returns_payment_url(fake_client, monkeypatch):
    merchant_id, raw_key = _merchant_and_key(fake_client, monkeypatch)

    response = client.post(
        "/v1/collections",
        headers=_headers(raw_key),
        json={
            "merchant_id": str(merchant_id),
            "amount": 50000,
            "currency": "TZS",
            "customer_name": "Grace Mwakalinga",
            "customer_phone": "255747730270",
            "reference": "ORDER-4821",
            "description": "Payment for order ORDER-4821",
            "redirect_url": "https://merchantstore.co.tz/thank-you",
            "cancel_url": "https://merchantstore.co.tz/payment-failed",
        },
    )

    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["reference"] == "ORDER-4821"
    assert data["status"] == "created"
    assert data["payment_url"].endswith(f"/pay/{fake_client.table('payment_links')._table.rows[0]['public_slug']}")

    # No collection or ledger movement yet — no method has been chosen.
    assert fake_client.table("collections")._table.rows == []
    assert fake_client.table("ledger_entries")._table.rows == []


def test_create_collection_blocked_when_collections_disabled(fake_client, monkeypatch):
    """ENABLE_COLLECTIONS=false (app/core/feature_flags.py) must block new
    collection creation without touching auth/idempotency — the check
    runs first in every collection-creating endpoint."""
    merchant_id, raw_key = _merchant_and_key(fake_client, monkeypatch)
    monkeypatch.setenv("ENABLE_COLLECTIONS", "false")
    get_settings.cache_clear()

    response = client.post(
        "/v1/collections",
        headers=_headers(raw_key),
        json={
            "merchant_id": str(merchant_id),
            "amount": 50000,
            "currency": "TZS",
            "customer_name": "Grace Mwakalinga",
            "customer_phone": "255747730270",
            "reference": "ORDER-4822",
        },
    )

    assert response.status_code == 503, response.text
    assert response.json()["error"]["code"] == "feature_disabled"
    assert fake_client.table("payment_links")._table.rows == []


def test_create_collection_wires_redirect_urls(fake_client, monkeypatch):
    merchant_id, raw_key = _merchant_and_key(fake_client, monkeypatch)

    client.post(
        "/v1/collections",
        headers=_headers(raw_key),
        json={
            "merchant_id": str(merchant_id),
            "amount": 1000,
            "redirect_url": "https://merchantstore.co.tz/thank-you",
            "cancel_url": "https://merchantstore.co.tz/payment-failed",
        },
    )

    link = fake_client.table("payment_links")._table.rows[0]
    assert link["success_redirect_url"] == "https://merchantstore.co.tz/thank-you"
    assert link["failure_redirect_url"] == "https://merchantstore.co.tz/payment-failed"


# --- POST /v1/collections/wallet-push ---------------------------------------------------


def test_wallet_push_sends_prompt_and_does_not_credit(fake_client, monkeypatch):
    merchant_id, raw_key = _merchant_and_key(fake_client, monkeypatch)

    response = client.post(
        "/v1/collections/wallet-push",
        headers=_headers(raw_key),
        json={
            "merchant_id": str(merchant_id),
            "amount": 50000,
            "phone": "255747730270",
            "customer_name": "Grace Mwakalinga",
            "reference": "ORDER-4821",
        },
    )

    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["status"] == "processing"
    assert data["message"] == "Payment prompt sent. Please approve on your phone."
    assert fake_client.table("ledger_entries")._table.rows == []

    collection = fake_client.table("collections")._table.rows[0]
    assert collection["method"] == "STK_PUSH"
    assert collection["merchant_reference"] == "ORDER-4821"


def test_wallet_push_requires_phone(fake_client, monkeypatch):
    merchant_id, raw_key = _merchant_and_key(fake_client, monkeypatch)

    response = client.post(
        "/v1/collections/wallet-push",
        headers=_headers(raw_key),
        json={"merchant_id": str(merchant_id), "amount": 50000},
    )
    assert response.status_code == 422, response.text


# --- POST /v1/collections/selcom-pesa ---------------------------------------------------


def test_selcom_pesa_sends_prompt_and_does_not_credit(fake_client, monkeypatch):
    merchant_id, raw_key = _merchant_and_key(fake_client, monkeypatch)

    response = client.post(
        "/v1/collections/selcom-pesa",
        headers=_headers(raw_key),
        json={
            "merchant_id": str(merchant_id),
            "amount": 50000,
            "phone": "255747730270",
            "customer_name": "Grace Mwakalinga",
            "reference": "ORDER-4821",
        },
    )

    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["status"] == "processing"
    assert data["message"] == "Selcom Pesa prompt sent. Please approve in your Selcom Pesa app."
    assert fake_client.table("ledger_entries")._table.rows == []

    collection = fake_client.table("collections")._table.rows[0]
    assert collection["method"] == "SELCOM_PESA_PUSH"


# --- POST /v1/collections/qr ------------------------------------------------------------


def test_qr_collection_returns_selcom_qr_and_token_only(fake_client, monkeypatch):
    merchant_id, raw_key = _merchant_and_key(fake_client, monkeypatch)

    response = client.post(
        "/v1/collections/qr",
        headers=_headers(raw_key),
        json={"merchant_id": str(merchant_id), "amount": 50000, "customer_name": "Grace", "reference": "ORDER-4821"},
    )

    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["status"] == "processing"
    assert data["qr_payload"] == "00020101021226580014COM.SELCOM.WWW"
    assert data["payment_token"] == "80008000"
    assert data["expires_at"] is None  # never fabricated — Selcom's real response has no expiry field
    assert fake_client.table("ledger_entries")._table.rows == []

    collection = fake_client.table("collections")._table.rows[0]
    assert collection["method"] == "DYNAMIC_QR"

    # Backend storage: the checkout_orders row keeps Selcom's raw qr/token.
    order = fake_client.table("checkout_orders")._table.rows[0]
    assert order["qr"] == "00020101021226580014COM.SELCOM.WWW"
    assert order["payment_token"] == "80008000"


def test_qr_collection_does_not_require_phone(fake_client, monkeypatch):
    merchant_id, raw_key = _merchant_and_key(fake_client, monkeypatch)

    response = client.post(
        "/v1/collections/qr",
        headers=_headers(raw_key),
        json={"merchant_id": str(merchant_id), "amount": 50000},
    )
    assert response.status_code == 202, response.text


# --- GET /v1/collections/{collection_id} ------------------------------------------------


def test_get_status_for_payment_page_with_no_method_chosen_yet(fake_client, monkeypatch):
    merchant_id, raw_key = _merchant_and_key(fake_client, monkeypatch)
    create_response = client.post(
        "/v1/collections", headers=_headers(raw_key), json={"merchant_id": str(merchant_id), "amount": 1000}
    )
    collection_id = create_response.json()["data"]["collection_id"]

    response = client.get(f"/v1/collections/{collection_id}", headers={"X-API-Key": raw_key}, params={"merchant_id": str(merchant_id)})

    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "created"
    assert response.json()["data"]["method"] is None


def test_get_status_for_a_real_collection(fake_client, monkeypatch):
    merchant_id, raw_key = _merchant_and_key(fake_client, monkeypatch)
    create_response = client.post(
        "/v1/collections/wallet-push",
        headers=_headers(raw_key),
        json={"merchant_id": str(merchant_id), "amount": 50000, "phone": "255747730270"},
    )
    collection_id = create_response.json()["data"]["collection_id"]

    response = client.get(f"/v1/collections/{collection_id}", headers={"X-API-Key": raw_key}, params={"merchant_id": str(merchant_id)})

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "processing"
    assert data["method"] == "wallet_push"


def test_get_status_404s_for_unknown_id(fake_client, monkeypatch):
    merchant_id, raw_key = _merchant_and_key(fake_client, monkeypatch)

    response = client.get(
        f"/v1/collections/{uuid.uuid4()}", headers={"X-API-Key": raw_key}, params={"merchant_id": str(merchant_id)}
    )
    assert response.status_code == 404, response.text


def test_get_status_404s_for_a_different_merchants_collection(fake_client, monkeypatch):
    merchant_id, raw_key = _merchant_and_key(fake_client, monkeypatch)
    create_response = client.post(
        "/v1/collections/wallet-push",
        headers=_headers(raw_key),
        json={"merchant_id": str(merchant_id), "amount": 50000, "phone": "255747730270"},
    )
    collection_id = create_response.json()["data"]["collection_id"]

    other_merchant_id, other_raw_key = _merchant_and_key(fake_client, monkeypatch)
    response = client.get(
        f"/v1/collections/{collection_id}",
        headers={"X-API-Key": other_raw_key},
        params={"merchant_id": str(other_merchant_id)},
    )
    assert response.status_code == 404, response.text


# --- POST /v1/collections/{collection_id}/refresh-status --------------------------------


def test_refresh_status_is_idempotent(fake_client, monkeypatch):
    merchant_id, raw_key = _merchant_and_key(fake_client, monkeypatch)
    create_response = client.post(
        "/v1/collections/wallet-push",
        headers=_headers(raw_key),
        json={"merchant_id": str(merchant_id), "amount": 50000, "phone": "255747730270"},
    )
    collection_id = create_response.json()["data"]["collection_id"]

    import app.services.checkout_reconciliation as reconciliation_module

    class _FakeStatusClient:
        def __init__(self, *, credentials=None):
            pass

        async def get_order_status(self, *, order_id):
            from app.services.selcom_checkout.parsing import parse_order_status_response

            return parse_order_status_response(
                {
                    "reference": "S1",
                    "resultcode": "000",
                    "result": "SUCCESS",
                    "message": "OK",
                    "data": [{"order_id": order_id, "payment_status": "COMPLETED"}],
                }
            )

    monkeypatch.setattr(reconciliation_module, "SelcomCheckoutHTTPClient", lambda **kw: _FakeStatusClient())

    first = client.post(f"/v1/collections/{collection_id}/refresh-status", params={"merchant_id": str(merchant_id)}, headers={"X-API-Key": raw_key})
    assert first.status_code == 200, first.text
    assert first.json()["data"]["status"] == "successful"

    wallet = fake_client.table("ledger_accounts")._table.rows[0] if fake_client.table("ledger_accounts")._table.rows else None
    balance_after_first = wallet["balance"] if wallet else None

    second = client.post(f"/v1/collections/{collection_id}/refresh-status", params={"merchant_id": str(merchant_id)}, headers={"X-API-Key": raw_key})
    assert second.status_code == 200, second.text
    assert second.json()["data"]["status"] == "successful"

    wallet_after_second = fake_client.table("ledger_accounts")._table.rows[0]["balance"]
    assert wallet_after_second == balance_after_first  # not double-credited

    # Regression: this endpoint never recorded "who/what triggered this
    # refresh" — found missing during the MVP-readiness audit-log sweep.
    # Logged on every call regardless of whether anything actually changed
    # (matching the existing admin.py::refresh_admin_collection_status
    # pattern) — the underlying resolve_collection() no-op is what keeps
    # the *wallet* from being double-credited, not this audit trail.
    refresh_events = [
        a for a in fake_client.table("audit_logs")._table.rows if a["action"] == "collection.status_refreshed"
    ]
    assert len(refresh_events) == 2


def test_refresh_status_noop_when_no_method_chosen_yet(fake_client, monkeypatch):
    merchant_id, raw_key = _merchant_and_key(fake_client, monkeypatch)
    create_response = client.post(
        "/v1/collections", headers=_headers(raw_key), json={"merchant_id": str(merchant_id), "amount": 1000}
    )
    collection_id = create_response.json()["data"]["collection_id"]

    response = client.post(
        f"/v1/collections/{collection_id}/refresh-status", params={"merchant_id": str(merchant_id)}, headers={"X-API-Key": raw_key}
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "created"
