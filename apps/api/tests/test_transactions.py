"""Flat, API-key-friendly GET /v1/transactions/{reference} — the developer
lookup-by-reference path for a merchant's own backend, distinct from the
dashboard-only /v1/merchants/{id}/transactions/{transaction_id} (by internal
UUID id) and /v1/merchant/transactions/{reference} (JWT-only, own-merchant)
routes. See tests/test_merchant_portal.py for the latter.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from tests.factories import TEST_JWT_SECRET, create_merchant, make_api_key

client = TestClient(app)


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _seed_transaction(fake_client, merchant_id: uuid.UUID, reference: str) -> dict:
    return fake_client.seed(
        "transactions",
        {
            "merchant_id": str(merchant_id),
            "reference": reference,
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


def test_get_transaction_by_reference_no_key_or_token_rejected(fake_client):
    response = client.get("/v1/transactions/TXN-ANYTHING")
    assert response.status_code == 401


def test_get_transaction_by_reference_via_api_key(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    _seed_transaction(fake_client, merchant_id, "TXN-API-1")
    raw_key, _ = make_api_key(fake_client, merchant_id, scopes=["transactions:read"])

    response = client.get("/v1/transactions/TXN-API-1", headers={"X-API-Key": raw_key})

    assert response.status_code == 200, response.text
    assert response.json()["data"]["reference"] == "TXN-API-1"


def test_get_transaction_by_reference_api_key_missing_scope_rejected(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    _seed_transaction(fake_client, merchant_id, "TXN-API-2")
    raw_key, _ = make_api_key(fake_client, merchant_id, scopes=["invoices:read"])

    response = client.get("/v1/transactions/TXN-API-2", headers={"X-API-Key": raw_key})

    assert response.status_code == 403
    assert "transactions:read" in response.json()["error"]["message"]


def test_get_transaction_by_reference_api_key_for_different_merchant_rejected(fake_client):
    merchant_a = create_merchant(fake_client, contact_email="a@example.com")
    merchant_b = create_merchant(fake_client, contact_email="b@example.com")
    _seed_transaction(fake_client, uuid.UUID(merchant_b["id"]), "TXN-API-3")
    raw_key, _ = make_api_key(fake_client, uuid.UUID(merchant_a["id"]), scopes=["transactions:read"])

    response = client.get("/v1/transactions/TXN-API-3", headers={"X-API-Key": raw_key})

    assert response.status_code == 403


def test_get_transaction_by_reference_not_found(fake_client):
    merchant = create_merchant(fake_client)
    raw_key, _ = make_api_key(fake_client, uuid.UUID(merchant["id"]), scopes=["transactions:read"])

    response = client.get("/v1/transactions/TXN-NOPE", headers={"X-API-Key": raw_key})

    assert response.status_code == 404
