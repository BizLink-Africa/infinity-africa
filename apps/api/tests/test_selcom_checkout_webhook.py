"""POST /v1/webhooks/selcom/checkout — Selcom Checkout's inbound webhook.
Builds real, correctly-signed deliveries using the exact same signer.py
functions the (inferred, not yet confirmed — see that module's
docstring) verification scheme is built from, so these tests prove the
sign/verify round-trip is internally consistent, not just that some
arbitrary header happens to be accepted.
"""

import asyncio
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services.selcom_checkout.signer import build_timestamp, sign_request
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


def _signed_headers(body: dict, *, api_secret: str = _API_SECRET) -> dict:
    signed_field_names = ["transid", "order_id", "reference", "result", "resultcode", "payment_status"]
    fields = {name: str(body[name]) for name in signed_field_names}
    timestamp = build_timestamp()
    ts, digest, signed_fields = sign_request(fields, digest_method="HS256", api_secret=api_secret, timestamp=timestamp)
    return {
        "Timestamp": ts,
        "Digest": digest,
        "Digest-Method": "HS256",
        "Signed-Fields": signed_fields,
    }


def _post_webhook(body: dict, headers: dict):
    return client.post("/v1/webhooks/selcom/checkout", json=body, headers=headers)


# --- valid delivery ------------------------------------------------------------------


def test_valid_webhook_credits_merchant_once(fake_client, monkeypatch):
    collection = _seed_pending_collection(fake_client, monkeypatch)
    body = _webhook_body(collection, payment_status="COMPLETED")
    headers = _signed_headers(body)

    response = _post_webhook(body, headers)

    assert response.status_code == 200, response.text
    balance = fake_client.table("ledger_accounts")._table.rows[0]["balance"]
    assert Decimal(str(balance)) == Decimal("985.00")
    assert fake_client.table("payment_links")._table.rows[0]["status"] == "PAID"


def test_duplicate_webhook_does_not_double_credit(fake_client, monkeypatch):
    collection = _seed_pending_collection(fake_client, monkeypatch)
    body = _webhook_body(collection, payment_status="COMPLETED")
    headers = _signed_headers(body)

    first = _post_webhook(body, headers)
    second = _post_webhook(body, headers)  # identical delivery, e.g. Selcom's own retry

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["data"]["status"] == "duplicate"
    balance = fake_client.table("ledger_accounts")._table.rows[0]["balance"]
    assert Decimal(str(balance)) == Decimal("985.00")


# --- signature verification -----------------------------------------------------------


def test_invalid_webhook_signature_rejected(fake_client, monkeypatch):
    collection = _seed_pending_collection(fake_client, monkeypatch)
    body = _webhook_body(collection, payment_status="COMPLETED")
    headers = _signed_headers(body, api_secret="wrong-secret")

    response = _post_webhook(body, headers)

    assert response.status_code == 401
    balance = fake_client.table("ledger_accounts")._table.rows[0]["balance"]
    assert Decimal(str(balance)) == Decimal(0)  # never credited


def test_missing_signature_headers_rejected(fake_client, monkeypatch):
    collection = _seed_pending_collection(fake_client, monkeypatch)
    body = _webhook_body(collection, payment_status="COMPLETED")

    response = _post_webhook(body, headers={})

    assert response.status_code == 401


def test_tampered_body_after_signing_is_rejected(fake_client, monkeypatch):
    collection = _seed_pending_collection(fake_client, monkeypatch)
    body = _webhook_body(collection, payment_status="COMPLETED")
    headers = _signed_headers(body)
    body["resultcode"] = "651"  # tampered after signing — digest no longer matches

    response = _post_webhook(body, headers)

    assert response.status_code == 401


# --- non-completed payment_status values: never credit --------------------------------


@pytest.mark.parametrize("payment_status", ["PENDING", "INPROGRESS"])
def test_still_pending_webhook_does_not_credit(fake_client, monkeypatch, payment_status):
    collection = _seed_pending_collection(fake_client, monkeypatch)
    body = _webhook_body(collection, payment_status=payment_status, result="PENDING", resultcode="111")
    headers = _signed_headers(body)

    response = _post_webhook(body, headers)

    assert response.status_code == 200, response.text
    balance = fake_client.table("ledger_accounts")._table.rows[0]["balance"]
    assert Decimal(str(balance)) == Decimal(0)
    assert fake_client.table("collections")._table.rows[0]["status"] == "processing"


@pytest.mark.parametrize("payment_status", ["CANCELLED", "USERCANCELLED", "REJECTED"])
def test_terminal_failed_webhook_does_not_credit(fake_client, monkeypatch, payment_status):
    collection = _seed_pending_collection(fake_client, monkeypatch)
    body = _webhook_body(collection, payment_status=payment_status, result="FAIL", resultcode="651")
    headers = _signed_headers(body)

    response = _post_webhook(body, headers)

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
    headers = _signed_headers(body)

    response = _post_webhook(body, headers)

    assert response.status_code == 404
