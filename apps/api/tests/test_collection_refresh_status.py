"""POST /v1/merchant/collections/{id}/refresh-status and
POST /v1/admin/collections/{id}/refresh-status — the manual
reconciliation path, independent of the webhook. Both call
app/services/checkout_reconciliation.py::refresh_checkout_collection_status,
which is already covered directly in test_checkout_reconciliation.py —
these tests are about the HTTP layer (auth/scoping) on top of it.
"""

import asyncio
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services.wallet_push import execute_wallet_push_for_payment_link
from tests.factories import (
    TEST_JWT_SECRET,
    auth_headers,
    create_merchant,
    make_merchant_member,
    make_super_admin,
)

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

ORDER_STATUS_COMPLETED_RESPONSE = {
    "reference": "S20690471578",
    "resultcode": "000",
    "result": "SUCCESS",
    "message": "OK",
    "data": [{"payment_status": "COMPLETED"}],
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

    async def get_order_status(self, *, order_id):
        from app.services.selcom_checkout.parsing import parse_order_status_response

        return parse_order_status_response(ORDER_STATUS_COMPLETED_RESPONSE)


def _seed_pending_collection(fake_client, monkeypatch):
    import app.services.checkout_orders as checkout_orders_module
    import app.services.checkout_reconciliation as reconciliation_module
    import app.services.wallet_push as wallet_push_module

    fake = _FakeSelcomCheckoutClient()
    monkeypatch.setattr(checkout_orders_module, "SelcomCheckoutHTTPClient", lambda **kwargs: fake)
    monkeypatch.setattr(wallet_push_module, "SelcomCheckoutHTTPClient", lambda **kwargs: fake)
    monkeypatch.setattr(reconciliation_module, "SelcomCheckoutHTTPClient", lambda **kwargs: fake)

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
    return collection, merchant_id, user_id


# --- merchant refresh-status -----------------------------------------------------------


def test_merchant_refresh_status_completes_and_credits(fake_client, monkeypatch):
    collection, _merchant_id, user_id = _seed_pending_collection(fake_client, monkeypatch)

    response = client.post(
        f"/v1/merchant/collections/{collection['id']}/refresh-status", headers=auth_headers(user_id)
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "successful"
    balance = fake_client.table("ledger_accounts")._table.rows[0]["balance"]
    assert Decimal(str(balance)) == Decimal("985.00")


def test_merchant_refresh_status_scoped_to_own_merchant(fake_client, monkeypatch):
    collection, _merchant_id, _user_id = _seed_pending_collection(fake_client, monkeypatch)

    other_merchant = create_merchant(fake_client)
    other_user_id = uuid.uuid4()
    make_merchant_member(fake_client, uuid.UUID(other_merchant["id"]), other_user_id, "MERCHANT_ADMIN")

    response = client.post(
        f"/v1/merchant/collections/{collection['id']}/refresh-status", headers=auth_headers(other_user_id)
    )

    assert response.status_code == 404


def test_merchant_refresh_status_twice_does_not_double_credit(fake_client, monkeypatch):
    collection, _merchant_id, user_id = _seed_pending_collection(fake_client, monkeypatch)

    client.post(f"/v1/merchant/collections/{collection['id']}/refresh-status", headers=auth_headers(user_id))
    client.post(f"/v1/merchant/collections/{collection['id']}/refresh-status", headers=auth_headers(user_id))

    balance = fake_client.table("ledger_accounts")._table.rows[0]["balance"]
    assert Decimal(str(balance)) == Decimal("985.00")


# --- admin refresh-status --------------------------------------------------------------


def test_admin_refresh_status_completes_and_credits(fake_client, monkeypatch):
    collection, _merchant_id, _user_id = _seed_pending_collection(fake_client, monkeypatch)
    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)

    response = client.post(
        f"/v1/admin/collections/{collection['id']}/refresh-status", headers=auth_headers(admin_id)
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "successful"
    balance = fake_client.table("ledger_accounts")._table.rows[0]["balance"]
    assert Decimal(str(balance)) == Decimal("985.00")


def test_admin_refresh_status_requires_super_admin(fake_client, monkeypatch):
    collection, _merchant_id, user_id = _seed_pending_collection(fake_client, monkeypatch)

    response = client.post(
        f"/v1/admin/collections/{collection['id']}/refresh-status", headers=auth_headers(user_id)
    )

    assert response.status_code == 403
