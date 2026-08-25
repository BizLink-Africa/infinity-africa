"""Sandbox-environment API keys must never touch real Selcom or the real
ledger — POST /v1/collections/{wallet-push,selcom-pesa,qr} routes a
sandbox key to a fully simulated flow instead. No SelcomCheckoutHTTPClient
patch is installed anywhere in this file on purpose: if sandbox code ever
accidentally reached the real client, these tests would error loudly
(NameError/AttributeError on an unmocked network call) rather than
silently pass.
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


def _merchant_with_key(fake_client, *, environment: str):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    raw_key, key_row = make_api_key(fake_client, merchant_id, environment=environment)
    return merchant_id, raw_key, key_row


def test_sandbox_wallet_push_never_calls_selcom_and_defaults_to_successful(fake_client):
    merchant_id, raw_key, key_row = _merchant_with_key(fake_client, environment="sandbox")

    response = client.post(
        "/v1/collections/wallet-push",
        headers={"X-API-Key": raw_key, "Idempotency-Key": str(uuid.uuid4())},
        json={"merchant_id": str(merchant_id), "amount": 1000, "phone": "255747730270"},
    )

    assert response.status_code == 202, response.text
    body = response.json()["data"]
    assert body["status"] == "successful"

    collection = fake_client.table("collections")._table.rows[0]
    assert collection["environment"] == "sandbox"
    assert collection["provider"] == "sandbox"
    assert collection["api_key_id"] == key_row["id"]
    assert collection["source"] == "API_WALLET_PUSH"

    # No transactions row -> resolve_collection()'s ledger-posting path is
    # structurally unreachable for this collection.
    assert fake_client.table("transactions")._table.rows == []
    assert fake_client.table("ledger_entries")._table.rows == []


def test_sandbox_simulate_status_controls_the_outcome(fake_client):
    merchant_id, raw_key, _key_row = _merchant_with_key(fake_client, environment="sandbox")

    response = client.post(
        "/v1/collections/wallet-push",
        headers={"X-API-Key": raw_key, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "merchant_id": str(merchant_id),
            "amount": 1000,
            "phone": "255747730270",
            "simulate_status": "failed",
        },
    )

    assert response.status_code == 202, response.text
    body = response.json()["data"]
    assert body["status"] == "failed"
    assert "Simulated failure" in body["message"] or "sandbox" in body["message"].lower()


def test_sandbox_simulate_status_pending_clearance_maps_to_pending_review_internally(fake_client):
    merchant_id, raw_key, _key_row = _merchant_with_key(fake_client, environment="sandbox")

    response = client.post(
        "/v1/collections/selcom-pesa",
        headers={"X-API-Key": raw_key, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "merchant_id": str(merchant_id),
            "amount": 1000,
            "phone": "255747730270",
            "simulate_status": "pending_clearance",
        },
    )
    assert response.status_code == 202, response.text
    assert response.json()["data"]["status"] == "pending_clearance"

    collection = fake_client.table("collections")._table.rows[0]
    assert collection["status"] == "pending_review"


def test_sandbox_qr_returns_a_synthetic_token_and_qr_payload(fake_client):
    merchant_id, raw_key, _key_row = _merchant_with_key(fake_client, environment="sandbox")

    response = client.post(
        "/v1/collections/qr",
        headers={"X-API-Key": raw_key, "Idempotency-Key": str(uuid.uuid4())},
        json={"merchant_id": str(merchant_id), "amount": 1000},
    )

    assert response.status_code == 202, response.text
    body = response.json()["data"]
    assert body["status"] == "successful"
    assert body["payment_token"] is not None
    assert body["qr_payload"] is not None


def test_simulate_status_rejected_for_a_live_key(fake_client):
    merchant_id, raw_key, _key_row = _merchant_with_key(fake_client, environment="live")

    response = client.post(
        "/v1/collections/wallet-push",
        headers={"X-API-Key": raw_key, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "merchant_id": str(merchant_id),
            "amount": 1000,
            "phone": "255747730270",
            "simulate_status": "successful",
        },
    )
    assert response.status_code == 422, response.text
    assert fake_client.table("collections")._table.rows == []


def test_a_live_key_cannot_read_a_sandbox_collection(fake_client):
    merchant_id, sandbox_key, _row = _merchant_with_key(fake_client, environment="sandbox")
    live_key, _live_row = make_api_key(fake_client, merchant_id, environment="live")

    create_response = client.post(
        "/v1/collections/wallet-push",
        headers={"X-API-Key": sandbox_key, "Idempotency-Key": str(uuid.uuid4())},
        json={"merchant_id": str(merchant_id), "amount": 1000, "phone": "255747730270"},
    )
    collection_id = create_response.json()["data"]["collection_id"]

    response = client.get(
        f"/v1/collections/{collection_id}?merchant_id={merchant_id}",
        headers={"X-API-Key": live_key},
    )
    assert response.status_code == 404, response.text


def test_a_sandbox_key_can_read_its_own_sandbox_collection(fake_client):
    merchant_id, sandbox_key, _row = _merchant_with_key(fake_client, environment="sandbox")

    create_response = client.post(
        "/v1/collections/wallet-push",
        headers={"X-API-Key": sandbox_key, "Idempotency-Key": str(uuid.uuid4())},
        json={"merchant_id": str(merchant_id), "amount": 1000, "phone": "255747730270"},
    )
    collection_id = create_response.json()["data"]["collection_id"]

    response = client.get(
        f"/v1/collections/{collection_id}?merchant_id={merchant_id}",
        headers={"X-API-Key": sandbox_key},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "successful"
