"""GET /public/payment-links/{slug}/collections/{collection_id}/receipt —
only ever serves data for a genuinely "successful" collection, and only
ever Selcom's own already-captured fields, never generated ones.
"""

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services.checkout_reconciliation import complete_checkout_collection_once
from app.services.wallet_push import execute_wallet_push_for_payment_link
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


def _patch_checkout_client(monkeypatch):
    import app.services.checkout_orders as checkout_orders_module
    import app.services.wallet_push as wallet_push_module

    fake = _FakeSelcomCheckoutClient()
    monkeypatch.setattr(checkout_orders_module, "SelcomCheckoutHTTPClient", lambda **kwargs: fake)
    monkeypatch.setattr(wallet_push_module, "SelcomCheckoutHTTPClient", lambda **kwargs: fake)


def _create_merchant_and_link(fake_client, monkeypatch, **link_overrides) -> tuple[dict, dict]:
    merchant = create_merchant(fake_client, business_name="Salome Mponeja Shop")
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
    body = {"merchant_id": str(merchant_id), "amount": "2500.00", "currency": "TZS", **link_overrides}
    response = client.post(
        "/v1/payment-links",
        headers={**auth_headers(admin_id), "Idempotency-Key": str(uuid.uuid4())},
        json=body,
    )
    assert response.status_code == 201, response.text
    return merchant, response.json()["data"]


def _complete_a_wallet_push_collection(fake_client, monkeypatch, link: dict) -> dict:
    _patch_checkout_client(monkeypatch)
    collection = asyncio.run(
        execute_wallet_push_for_payment_link(fake_client, payment_link=link, buyer_phone="255747730270")
    )
    asyncio.run(
        complete_checkout_collection_once(
            fake_client,
            collection_id=uuid.UUID(collection["id"]),
            payment_status="COMPLETED",
            result="SUCCESS",
            resultcode="000",
            reference="S20690471578",
            transid=collection["provider_transid"],
            channel="TIGOPESA",
            raw_response={
                "payment_status": "COMPLETED",
                "api_key": "should-never-reach-the-receipt",
                "private_key": "should-never-reach-the-receipt",
            },
        )
    )
    return collection


def test_receipt_available_for_successful_collection(fake_client, monkeypatch):
    _merchant, link = _create_merchant_and_link(
        fake_client, monkeypatch, description="Test invoice", merchant_reference="INV-2026-0042"
    )
    collection = _complete_a_wallet_push_collection(fake_client, monkeypatch, link)

    response = client.get(f"/public/payment-links/{link['public_slug']}/collections/{collection['id']}/receipt")

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["merchant_name"] == "Salome Mponeja Shop"
    assert data["amount"] == "2500.00"
    assert data["currency"] == "TZS"
    assert data["description"] == "Test invoice"
    assert data["method"] == "Mobile Money Push"
    assert data["channel"] == "TIGOPESA"
    assert data["provider_reference"] == "S20690471578"
    assert data["completed_at"] is not None
    assert data["merchant_reference"] == "INV-2026-0042"


def test_receipt_does_not_expose_secrets_or_raw_provider_payload(fake_client, monkeypatch):
    """The completed collection's raw_response (captured above with
    fake secret-shaped values baked in, mirroring what a real Selcom
    payload capture could contain) must never leak through the public
    receipt response — only the specific fields
    PublicCollectionReceiptResponse declares are ever serialized."""
    _merchant, link = _create_merchant_and_link(fake_client, monkeypatch)
    collection = _complete_a_wallet_push_collection(fake_client, monkeypatch, link)

    response = client.get(f"/public/payment-links/{link['public_slug']}/collections/{collection['id']}/receipt")

    assert response.status_code == 200, response.text
    body_text = response.text
    assert "api_key" not in body_text
    assert "private_key" not in body_text
    assert "should-never-reach-the-receipt" not in body_text
    assert "raw_response" not in response.json()["data"]


def test_receipt_not_available_while_still_processing(fake_client, monkeypatch):
    _patch_checkout_client(monkeypatch)
    _merchant, link = _create_merchant_and_link(fake_client, monkeypatch)
    collection = asyncio.run(
        execute_wallet_push_for_payment_link(fake_client, payment_link=link, buyer_phone="255747730270")
    )
    assert collection["status"] == "processing"

    response = client.get(f"/public/payment-links/{link['public_slug']}/collections/{collection['id']}/receipt")
    assert response.status_code == 409, response.text


def test_receipt_not_available_for_failed_collection(fake_client, monkeypatch):
    _patch_checkout_client(monkeypatch)
    _merchant, link = _create_merchant_and_link(fake_client, monkeypatch)
    collection = asyncio.run(
        execute_wallet_push_for_payment_link(fake_client, payment_link=link, buyer_phone="255747730270")
    )
    asyncio.run(
        complete_checkout_collection_once(
            fake_client,
            collection_id=uuid.UUID(collection["id"]),
            payment_status="REJECTED",
            result="FAIL",
            resultcode="651",
            reference="ref",
            transid=collection["provider_transid"],
            channel="TIGOPESA",
            raw_response={},
        )
    )

    response = client.get(f"/public/payment-links/{link['public_slug']}/collections/{collection['id']}/receipt")
    assert response.status_code == 409, response.text


def test_receipt_not_available_for_reversed_collection(fake_client, monkeypatch):
    """A collection that was successful and later reversed must never
    keep serving a receipt — same 409 as processing/failed, not the
    "successful" branch."""
    _merchant, link = _create_merchant_and_link(fake_client, monkeypatch)
    collection = _complete_a_wallet_push_collection(fake_client, monkeypatch, link)
    from app.services.collections import reverse_successful_collection

    reverse_successful_collection(fake_client, collection_id=uuid.UUID(collection["id"]), reason="Reversed by provider")

    response = client.get(f"/public/payment-links/{link['public_slug']}/collections/{collection['id']}/receipt")
    assert response.status_code == 409, response.text


def test_receipt_404s_for_unknown_slug(fake_client):
    response = client.get(f"/public/payment-links/does-not-exist/collections/{uuid.uuid4()}/receipt")
    assert response.status_code == 404, response.text


def test_receipt_404s_for_collection_belonging_to_a_different_link(fake_client, monkeypatch):
    _merchant_a, link_a = _create_merchant_and_link(fake_client, monkeypatch)
    collection_a = _complete_a_wallet_push_collection(fake_client, monkeypatch, link_a)

    _merchant_b, link_b = _create_merchant_and_link(fake_client, monkeypatch)

    response = client.get(f"/public/payment-links/{link_b['public_slug']}/collections/{collection_a['id']}/receipt")
    assert response.status_code == 404, response.text
