"""POST /v1/webhooks/selcom/checkout — Selcom Checkout's inbound webhook.

Confirmed against 5 independent real deliveries on 2026-08-27: Selcom
sends no signature at all on this callback (no Digest/Timestamp/
Digest-Method/Signed-Fields header, or anything else signature-shaped).
The webhook therefore never trusts its own payload for crediting —
regardless of what it claims (result/resultcode/payment_status), or
whether it's "signed" at all, a delivery is only ever a "something may
have changed, go check" signal: it triggers a real, authenticated lookup
against Selcom's own order-status API
(app/services/checkout_reconciliation.py::resolve_checkout_collection_from_webhook_hint),
and only *that* answer ever gets applied. These tests prove that
property directly — a forged/tampered/unsigned POST that claims success
must never credit anything unless the authenticated lookup itself agrees.
"""

import asyncio
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services.wallet_push import execute_wallet_push_for_payment_link
from tests.factories import TEST_JWT_SECRET, create_merchant, make_merchant_member

client = TestClient(app)

_API_SECRET = "test-webhook-secret"

CREATE_ORDER_SUCCESS_RESPONSE = {
    "reference": "S20690427372",
    "resultcode": "000",
    "result": "SUCCESS",
    "message": "Payment notification logged",
    "data": [{"payment_token": "TOKEN", "payment_gateway_url": "aHR0cHM6Ly9leGFtcGxlLmNvbS9wYXk=", "qr": "QR"}],
}

WALLET_PAYMENT_PENDING_RESPONSE = {
    "reference": "0289999288",
    "resultcode": "111",
    "result": "PENDING",
    "message": "Request in progress.",
    "data": [],
}


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("SELCOM_CHECKOUT_BASE_URL", "https://checkout.example.selcommobile.com")
    monkeypatch.setenv("SELCOM_CHECKOUT_API_KEY", "test-key")
    monkeypatch.setenv("SELCOM_CHECKOUT_API_SECRET", _API_SECRET)
    monkeypatch.setenv("SELCOM_CHECKOUT_VENDOR", "VENDORTEST")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class _FakeSelcomCheckoutClient:
    async def create_order_minimal(self, **kwargs):
        from app.services.selcom_checkout.parsing import (
            parse_create_order_minimal_response,
        )

        return parse_create_order_minimal_response(CREATE_ORDER_SUCCESS_RESPONSE)

    async def process_wallet_payment(self, **kwargs):
        from app.services.selcom_checkout.parsing import parse_wallet_payment_response

        return parse_wallet_payment_response(WALLET_PAYMENT_PENDING_RESPONSE)


def _seed_pending_collection(fake_client, monkeypatch) -> dict:
    import app.services.checkout_orders as checkout_orders_module
    import app.services.wallet_push as wallet_push_module

    fake = _FakeSelcomCheckoutClient()
    monkeypatch.setattr(checkout_orders_module, "SelcomCheckoutHTTPClient", lambda **kwargs: fake)
    monkeypatch.setattr(wallet_push_module, "SelcomCheckoutHTTPClient", lambda **kwargs: fake)

    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    user_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, user_id, "MERCHANT_ADMIN")
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
    payment_link = fake_client.seed(
        "payment_links",
        {
            "merchant_id": str(merchant_id),
            "amount": "1000.00",
            "currency": "TZS",
            "status": "ACTIVE",
            "allowed_payment_methods": ["STK_PUSH"],
            "public_slug": "test-slug-" + uuid.uuid4().hex[:8],
        },
    )
    collection = asyncio.run(
        execute_wallet_push_for_payment_link(fake_client, payment_link=payment_link, buyer_phone="255747730270")
    )
    assert collection["status"] == "processing"
    return collection


def _webhook_body(collection: dict, *, payment_status: str, result: str = "SUCCESS", resultcode: str = "000") -> dict:
    """The claims a webhook delivery carries — never trusted directly by
    the handler; only transid/order_id are used, to find the collection
    and to know which Selcom order to ask about."""
    return {
        "transid": collection["provider_transid"],
        "order_id": "irrelevant-not-matched-by-order-id-in-these-tests",
        "reference": "S20690471578",
        "result": result,
        "resultcode": resultcode,
        "payment_status": payment_status,
        "channel": "TIGOPESA",
        "amount": "1000.00",
        "phone": "255747730270",
    }


def _stub_order_status(monkeypatch, *, payment_status: str, result: str = "SUCCESS", resultcode: str = "000"):
    """Patches the *authenticated outbound* lookup the webhook now always
    triggers — this, not the webhook body, is what actually decides the
    outcome."""
    import app.services.checkout_reconciliation as reconciliation_module

    class _FakeStatusClient:
        def __init__(self, *, credentials=None):
            pass

        async def get_order_status(self, *, order_id):
            from app.services.selcom_checkout.parsing import parse_order_status_response

            return parse_order_status_response(
                {
                    "reference": "S20690471578",
                    "resultcode": resultcode,
                    "result": result,
                    "message": "OK",
                    "data": [{"order_id": order_id, "payment_status": payment_status}],
                }
            )

    monkeypatch.setattr(reconciliation_module, "SelcomCheckoutHTTPClient", lambda **kwargs: _FakeStatusClient())


def _post_webhook(body: dict, headers: dict | None = None):
    return client.post("/v1/webhooks/selcom/checkout", json=body, headers=headers or {})


# --- the webhook never trusts its own payload -------------------------------------------


def test_unsigned_delivery_credits_when_the_authenticated_lookup_agrees(fake_client, monkeypatch):
    """No signature at all (matches every real delivery) — still credits,
    because the authenticated Selcom lookup independently confirms it."""
    collection = _seed_pending_collection(fake_client, monkeypatch)
    _stub_order_status(monkeypatch, payment_status="COMPLETED")
    body = _webhook_body(collection, payment_status="COMPLETED")

    response = _post_webhook(body)  # no headers at all

    assert response.status_code == 200, response.text
    balance = fake_client.table("ledger_accounts")._table.rows[0]["balance"]
    assert Decimal(str(balance)) == Decimal("985.00")
    assert fake_client.table("payment_links")._table.rows[0]["status"] == "PAID"


def test_webhook_claiming_success_is_ignored_if_selcom_actually_says_pending(fake_client, monkeypatch):
    """The core security property: a delivery's own claimed
    result/resultcode/payment_status can never force a credit — only the
    authenticated lookup's answer matters. Proves a forged/replayed POST
    to this URL can't move money on its own."""
    collection = _seed_pending_collection(fake_client, monkeypatch)
    _stub_order_status(monkeypatch, payment_status="PENDING", result="PENDING", resultcode="111")
    body = _webhook_body(collection, payment_status="COMPLETED", result="SUCCESS", resultcode="000")

    response = _post_webhook(body)

    assert response.status_code == 200, response.text
    balance = fake_client.table("ledger_accounts")._table.rows[0]["balance"]
    assert Decimal(str(balance)) == Decimal(0)  # never credited on the delivery's own say-so
    assert fake_client.table("collections")._table.rows[0]["status"] == "processing"


def test_duplicate_webhook_does_not_double_credit(fake_client, monkeypatch):
    collection = _seed_pending_collection(fake_client, monkeypatch)
    _stub_order_status(monkeypatch, payment_status="COMPLETED")
    body = _webhook_body(collection, payment_status="COMPLETED")

    first = _post_webhook(body)
    second = _post_webhook(body)  # identical delivery, e.g. Selcom's own retry

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["data"]["status"] == "duplicate"
    balance = fake_client.table("ledger_accounts")._table.rows[0]["balance"]
    assert Decimal(str(balance)) == Decimal("985.00")


# --- signature is stored for audit, never a rejection reason -----------------------------


def test_missing_signature_headers_does_not_block_processing(fake_client, monkeypatch):
    """Matches every real delivery this backend has ever received —
    Selcom sends none of these headers. Must not 401."""
    collection = _seed_pending_collection(fake_client, monkeypatch)
    _stub_order_status(monkeypatch, payment_status="COMPLETED")
    body = _webhook_body(collection, payment_status="COMPLETED")

    response = _post_webhook(body, headers={})

    assert response.status_code == 200, response.text


def test_signature_valid_is_recorded_false_but_still_processed(fake_client, monkeypatch):
    collection = _seed_pending_collection(fake_client, monkeypatch)
    _stub_order_status(monkeypatch, payment_status="COMPLETED")
    body = _webhook_body(collection, payment_status="COMPLETED")

    response = _post_webhook(body, headers={"X-Some-Other-Header": "value"})

    assert response.status_code == 200, response.text
    event = fake_client.table("selcom_webhook_events")._table.rows[-1]
    assert event["signature_valid"] is False
    assert event["status"] == "processed"


def test_raw_headers_stored_for_diagnosis(fake_client, monkeypatch):
    """Added after the first real delivery on 2026-08-22 arrived with the
    expected signing headers completely absent, and there was no stored
    evidence of what Selcom actually sent instead. Never stores
    Authorization/Cookie, defensively (a provider webhook has no
    legitimate reason to carry either)."""
    collection = _seed_pending_collection(fake_client, monkeypatch)
    _stub_order_status(monkeypatch, payment_status="COMPLETED")
    body = _webhook_body(collection, payment_status="COMPLETED")

    response = _post_webhook(
        body, headers={"X-Some-Other-Header": "value", "Authorization": "Bearer should-never-be-stored"}
    )

    assert response.status_code == 200, response.text
    event = fake_client.table("selcom_webhook_events")._table.rows[-1]
    assert "x-some-other-header" in event["raw_headers"]
    assert "authorization" not in event["raw_headers"]


# --- authenticated lookup result decides everything ---------------------------------------


@pytest.mark.parametrize("payment_status", ["PENDING", "INPROGRESS"])
def test_still_pending_lookup_result_does_not_credit(fake_client, monkeypatch, payment_status):
    collection = _seed_pending_collection(fake_client, monkeypatch)
    _stub_order_status(monkeypatch, payment_status=payment_status, result="PENDING", resultcode="111")
    body = _webhook_body(collection, payment_status=payment_status, result="PENDING", resultcode="111")

    response = _post_webhook(body)

    assert response.status_code == 200, response.text
    balance = fake_client.table("ledger_accounts")._table.rows[0]["balance"]
    assert Decimal(str(balance)) == Decimal(0)
    assert fake_client.table("collections")._table.rows[0]["status"] == "processing"


@pytest.mark.parametrize("payment_status", ["CANCELLED", "USERCANCELLED", "REJECTED"])
def test_terminal_failed_lookup_result_does_not_credit(fake_client, monkeypatch, payment_status):
    collection = _seed_pending_collection(fake_client, monkeypatch)
    _stub_order_status(monkeypatch, payment_status=payment_status, result="FAIL", resultcode="651")
    body = _webhook_body(collection, payment_status=payment_status, result="FAIL", resultcode="651")

    response = _post_webhook(body)

    assert response.status_code == 200, response.text
    balance = fake_client.table("ledger_accounts")._table.rows[0]["balance"]
    assert Decimal(str(balance)) == Decimal(0)
    assert fake_client.table("collections")._table.rows[0]["status"] == "failed"


# --- unmatched delivery ----------------------------------------------------------------


def test_unmatched_transid_returns_404(fake_client, monkeypatch):
    _seed_pending_collection(fake_client, monkeypatch)  # exists, but body below references a different transid
    body = {
        "transid": "TXN-DOES-NOT-EXIST",
        "order_id": "ORD-DOES-NOT-EXIST",
        "reference": "REF-1",
        "result": "SUCCESS",
        "resultcode": "000",
        "payment_status": "COMPLETED",
    }

    response = _post_webhook(body)

    assert response.status_code == 404
