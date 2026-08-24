"""Merchant ownership + payment source tracking — every collection must
belong to exactly one merchant, that merchant_id must never be spoofable
by the caller, and collections.source/api_key_id must correctly record
which product surface and (if applicable) which API key created it.
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
    make_api_key,
    make_merchant_member,
)

client = TestClient(app)


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

        return parse_create_order_minimal_response(
            {
                "reference": "S20690900000",
                "resultcode": "000",
                "result": "SUCCESS",
                "message": "Payment notification logged",
                "data": [{"payment_token": "TOKEN", "qr": "QR", "payment_gateway_url": "aHR0cHM6Ly9leGFtcGxlLmNvbS9wYXk="}],
            }
        )

    async def process_wallet_payment(self, **kwargs):
        from app.services.selcom_checkout.parsing import parse_wallet_payment_response

        return parse_wallet_payment_response(
            {"reference": "r1", "resultcode": "111", "result": "PENDING", "message": "Request in progress.", "data": []}
        )


def _patch_checkout_client(monkeypatch):
    import app.services.checkout_orders as checkout_orders_module
    import app.services.wallet_push as wallet_push_module

    fake = _FakeSelcomCheckoutClient()
    monkeypatch.setattr(checkout_orders_module, "SelcomCheckoutHTTPClient", lambda **kw: fake)
    monkeypatch.setattr(wallet_push_module, "SelcomCheckoutHTTPClient", lambda **kw: fake)


def _merchant_with_key(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    raw_key, key_row = make_api_key(fake_client, merchant_id)
    return merchant_id, raw_key, key_row


# --- API key ownership cannot be spoofed ------------------------------------------------


def test_api_key_for_merchant_a_cannot_create_collection_for_merchant_b(fake_client, monkeypatch):
    _patch_checkout_client(monkeypatch)
    _merchant_a_id, raw_key_a, _key_a = _merchant_with_key(fake_client)
    merchant_b = create_merchant(fake_client)
    merchant_b_id = uuid.UUID(merchant_b["id"])

    response = client.post(
        "/v1/collections/wallet-push",
        headers={"X-API-Key": raw_key_a, "Idempotency-Key": str(uuid.uuid4())},
        json={"merchant_id": str(merchant_b_id), "amount": 1000, "phone": "255747730270"},
    )

    assert response.status_code == 403, response.text
    assert fake_client.table("collections")._table.rows == []


def test_merchant_id_in_request_body_cannot_override_the_api_keys_own_merchant(fake_client, monkeypatch):
    """The body's merchant_id is checked against the API key's real
    merchant, never trusted outright — a mismatch is rejected (403),
    which satisfies "ignored or rejected": the value never takes
    effect either way."""
    _patch_checkout_client(monkeypatch)
    merchant_a_id, raw_key_a, _key_a = _merchant_with_key(fake_client)
    merchant_b = create_merchant(fake_client)
    merchant_b_id = uuid.UUID(merchant_b["id"])

    response = client.post(
        "/v1/collections",
        headers={"X-API-Key": raw_key_a, "Idempotency-Key": str(uuid.uuid4())},
        json={"merchant_id": str(merchant_b_id), "amount": 1000},
    )

    assert response.status_code == 403, response.text
    # Confirm the correct merchant_id (A's own) DOES work with the same key.
    ok_response = client.post(
        "/v1/collections",
        headers={"X-API-Key": raw_key_a, "Idempotency-Key": str(uuid.uuid4())},
        json={"merchant_id": str(merchant_a_id), "amount": 1000},
    )
    assert ok_response.status_code == 202, ok_response.text
    link = fake_client.table("payment_links")._table.rows[0]
    assert link["merchant_id"] == str(merchant_a_id)


def test_revoked_api_key_cannot_create_collection(fake_client, monkeypatch):
    _patch_checkout_client(monkeypatch)
    merchant_id, raw_key, key_row = _merchant_with_key(fake_client)
    key_row["status"] = "revoked"  # simulate revocation directly on the seeded row

    response = client.post(
        "/v1/collections/wallet-push",
        headers={"X-API-Key": raw_key, "Idempotency-Key": str(uuid.uuid4())},
        json={"merchant_id": str(merchant_id), "amount": 1000, "phone": "255747730270"},
    )

    assert response.status_code == 401, response.text
    assert fake_client.table("collections")._table.rows == []


# --- source / api_key_id tracking --------------------------------------------------------


def test_api_wallet_push_collection_records_source_and_api_key_id(fake_client, monkeypatch):
    _patch_checkout_client(monkeypatch)
    merchant_id, raw_key, key_row = _merchant_with_key(fake_client)

    response = client.post(
        "/v1/collections/wallet-push",
        headers={"X-API-Key": raw_key, "Idempotency-Key": str(uuid.uuid4())},
        json={"merchant_id": str(merchant_id), "amount": 1000, "phone": "255747730270"},
    )
    assert response.status_code == 202, response.text

    collection = fake_client.table("collections")._table.rows[0]
    assert collection["source"] == "API_WALLET_PUSH"
    assert collection["api_key_id"] == key_row["id"]
    assert collection["merchant_id"] == str(merchant_id)


def test_infinity_payment_page_collection_records_api_source_once_a_method_is_chosen(fake_client, monkeypatch):
    """POST /v1/collections creates a payment_links row (source isn't
    knowable yet — no collection exists). Once the customer picks a
    method on that page, the resulting collection's source must be
    API_PAYMENT_PAGE (not plain PAYMENT_LINK), because the page itself
    was created via the API."""
    _patch_checkout_client(monkeypatch)
    merchant_id, raw_key, key_row = _merchant_with_key(fake_client)

    create_response = client.post(
        "/v1/collections",
        headers={"X-API-Key": raw_key, "Idempotency-Key": str(uuid.uuid4())},
        json={"merchant_id": str(merchant_id), "amount": 1000},
    )
    assert create_response.status_code == 202, create_response.text
    payment_url = create_response.json()["data"]["payment_url"]
    slug = payment_url.rstrip("/").rsplit("/", 1)[-1]

    link_row = fake_client.table("payment_links")._table.rows[0]
    assert link_row["created_via"] == "api"
    assert link_row["api_key_id"] == key_row["id"]

    pay_response = client.post(
        f"/public/payment-links/{slug}/pay",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"method": "WALLET_PUSH", "customer_phone": "255747730270"},
    )
    assert pay_response.status_code == 202, pay_response.text

    collection = fake_client.table("collections")._table.rows[0]
    assert collection["source"] == "API_PAYMENT_PAGE"
    assert collection["merchant_id"] == str(merchant_id)


def test_dashboard_request_collection_records_dashboard_source(fake_client, monkeypatch):
    """Merchant Portal's "Request Collection" form creates a
    payment_links row with created_via='request_collection' — once the
    customer picks a method, the collection's source must be
    DASHBOARD_REQUEST, distinguishing it from a genuine Payment Link."""
    _patch_checkout_client(monkeypatch)
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    user_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, user_id, "MERCHANT_ADMIN")

    create_response = client.post(
        "/v1/merchant/payment-links",
        headers={**auth_headers(user_id), "Idempotency-Key": str(uuid.uuid4())},
        json={"amount": "1000.00", "origin": "request_collection"},
    )
    assert create_response.status_code == 201, create_response.text
    slug = create_response.json()["data"]["public_slug"]

    link_row = fake_client.table("payment_links")._table.rows[0]
    assert link_row["created_via"] == "request_collection"

    pay_response = client.post(
        f"/public/payment-links/{slug}/pay",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"method": "WALLET_PUSH", "customer_phone": "255747730270"},
    )
    assert pay_response.status_code == 202, pay_response.text

    collection = fake_client.table("collections")._table.rows[0]
    assert collection["source"] == "DASHBOARD_REQUEST"
    assert collection["merchant_id"] == str(merchant_id)


def test_genuine_payment_link_collection_records_payment_link_source(fake_client, monkeypatch):
    _patch_checkout_client(monkeypatch)
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    user_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, user_id, "MERCHANT_ADMIN")

    create_response = client.post(
        "/v1/merchant/payment-links",
        headers={**auth_headers(user_id), "Idempotency-Key": str(uuid.uuid4())},
        json={"amount": "1000.00"},
    )
    assert create_response.status_code == 201, create_response.text
    slug = create_response.json()["data"]["public_slug"]

    link_row = fake_client.table("payment_links")._table.rows[0]
    assert link_row["created_via"] == "payment_link"

    pay_response = client.post(
        f"/public/payment-links/{slug}/pay",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"method": "WALLET_PUSH", "customer_phone": "255747730270"},
    )
    assert pay_response.status_code == 202, pay_response.text

    collection = fake_client.table("collections")._table.rows[0]
    assert collection["source"] == "PAYMENT_LINK"
    assert collection["merchant_id"] == str(merchant_id)


def test_invoice_payment_collection_belongs_to_correct_merchant_and_records_invoice_source(fake_client, monkeypatch):
    _patch_checkout_client(monkeypatch)
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    user_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, user_id, "MERCHANT_ADMIN")

    create_response = client.post(
        "/v1/invoices",
        headers={**auth_headers(user_id), "Idempotency-Key": str(uuid.uuid4())},
        json={
            "merchant_id": str(merchant_id),
            "due_date": "2026-09-01",
            "items": [{"description": "Consulting", "quantity": "1", "unit_price": "1000.00"}],
        },
    )
    assert create_response.status_code == 201, create_response.text
    invoice_id = create_response.json()["data"]["id"]

    send_response = client.post(f"/v1/invoices/{invoice_id}/send", headers=auth_headers(user_id))
    assert send_response.status_code == 200, send_response.text

    link_response = client.post(f"/v1/invoices/{invoice_id}/payment-link", headers=auth_headers(user_id))
    assert link_response.status_code == 200, link_response.text
    slug = link_response.json()["data"]["public_slug"]

    pay_response = client.post(
        f"/public/payment-links/{slug}/pay",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"method": "WALLET_PUSH", "customer_phone": "255747730270"},
    )
    assert pay_response.status_code == 202, pay_response.text

    collection = fake_client.table("collections")._table.rows[0]
    assert collection["source"] == "INVOICE"
    assert collection["merchant_id"] == str(merchant_id)
    assert collection["invoice_id"] == invoice_id
