"""GET /public/payment-links/{public_slug}/collections/{collection_id}/status
— the customer payment page's polling target for the 6 states task 6
asks for (pending/completed/failed/cancelled/user_cancelled/rejected).
"""

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services.wallet_push import execute_wallet_push_for_payment_link
from tests.factories import TEST_JWT_SECRET, create_merchant, make_merchant_member

client = TestClient(app)

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
    monkeypatch.setenv("SELCOM_CHECKOUT_API_SECRET", "test-secret")
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


def _seed_pending_collection(fake_client, monkeypatch):
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
    slug = "test-slug-" + uuid.uuid4().hex[:8]
    payment_link = fake_client.seed(
        "payment_links",
        {
            "merchant_id": str(merchant_id),
            "amount": "1000.00",
            "currency": "TZS",
            "status": "ACTIVE",
            "allowed_payment_methods": ["STK_PUSH"],
            "public_slug": slug,
        },
    )
    collection = asyncio.run(
        execute_wallet_push_for_payment_link(fake_client, payment_link=payment_link, buyer_phone="255747730270")
    )
    return slug, collection


def test_pending_status(fake_client, monkeypatch):
    slug, collection = _seed_pending_collection(fake_client, monkeypatch)
    response = client.get(f"/public/payment-links/{slug}/collections/{collection['id']}/status")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "pending"


@pytest.mark.parametrize(
    ("row_status", "provider_payment_status", "expected"),
    [
        ("successful", "COMPLETED", "completed"),
        ("failed", "CANCELLED", "cancelled"),
        ("failed", "USERCANCELLED", "user_cancelled"),
        ("failed", "REJECTED", "rejected"),
        ("failed", None, "failed"),
    ],
)
def test_terminal_statuses(fake_client, monkeypatch, row_status, provider_payment_status, expected):
    slug, collection = _seed_pending_collection(fake_client, monkeypatch)
    row = fake_client.table("collections")._table.rows[0]
    row["status"] = row_status
    row["provider_payment_status"] = provider_payment_status

    response = client.get(f"/public/payment-links/{slug}/collections/{collection['id']}/status")

    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == expected


def test_collection_from_a_different_payment_link_is_not_found(fake_client, monkeypatch):
    slug, _collection = _seed_pending_collection(fake_client, monkeypatch)
    _other_slug, other_collection = _seed_pending_collection(fake_client, monkeypatch)

    response = client.get(f"/public/payment-links/{slug}/collections/{other_collection['id']}/status")
    assert response.status_code == 404
