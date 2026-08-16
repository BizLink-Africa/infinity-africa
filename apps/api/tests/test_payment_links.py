"""Payment Links module: creation, expiry, cancellation, and public lookup —
end to end against the in-memory FakeSupabaseClient (see tests/fakes.py).
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services.selcom.client import get_selcom_client
from tests.factories import (
    TEST_JWT_SECRET,
    auth_headers,
    create_merchant,
    make_api_key,
    make_merchant_member,
    make_super_admin,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("MOCK_PROVIDER_FAILURE_RATE", "0")
    monkeypatch.setenv("MOCK_PROVIDER_LATENCY_SECONDS", "0")
    get_settings.cache_clear()
    get_selcom_client.cache_clear()
    yield
    get_settings.cache_clear()
    get_selcom_client.cache_clear()


def _create_link(fake_client, merchant_id: uuid.UUID, user_id: uuid.UUID, **overrides) -> dict:
    body = {"merchant_id": str(merchant_id), "amount": "1000.00", "currency": "TZS", **overrides}
    response = client.post(
        "/v1/payment-links",
        headers={**auth_headers(user_id), "Idempotency-Key": str(uuid.uuid4())},
        json=body,
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _row(fake_client, link_id: str) -> dict:
    return next(r for r in fake_client.table("payment_links")._table.rows if r["id"] == link_id)


def _expire(fake_client, link_id: str) -> None:
    """Simulates time passing, rather than creating an already-expired link
    (nothing stops a real merchant from setting a near-future expires_at
    that then elapses — this is the realistic path)."""
    _row(fake_client, link_id)["expires_at"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()


# --- creation ----------------------------------------------------------------


def test_create_payment_link_via_dashboard_jwt(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    staff_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, staff_id, "MERCHANT_STAFF")

    link = _create_link(
        fake_client,
        merchant_id,
        staff_id,
        customer_name="Amina",
        customer_phone="+255700000000",
        description="Order #1",
        allowed_payment_methods=["STK_PUSH", "DYNAMIC_QR"],
    )

    assert link["status"] == "ACTIVE"
    assert link["merchant_id"] == str(merchant_id)
    assert link["customer_name"] == "Amina"
    assert link["allowed_payment_methods"] == ["STK_PUSH", "DYNAMIC_QR"]
    assert link["public_slug"]
    assert link["public_url"].endswith(f"/pay/{link['public_slug']}")


def test_create_payment_link_via_api_key(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    raw_key, _ = make_api_key(fake_client, merchant_id)

    response = client.post(
        "/v1/payment-links",
        headers={"X-API-Key": raw_key, "Idempotency-Key": str(uuid.uuid4())},
        json={"merchant_id": str(merchant_id), "amount": "500.00"},
    )

    assert response.status_code == 201, response.text
    assert response.json()["data"]["merchant_id"] == str(merchant_id)


def test_create_payment_link_api_key_for_different_merchant_rejected(fake_client):
    merchant_a = create_merchant(fake_client, contact_email="a@example.com")
    merchant_b = create_merchant(fake_client, contact_email="b@example.com")
    raw_key, _ = make_api_key(fake_client, uuid.UUID(merchant_a["id"]))

    response = client.post(
        "/v1/payment-links",
        headers={"X-API-Key": raw_key, "Idempotency-Key": str(uuid.uuid4())},
        json={"merchant_id": merchant_b["id"], "amount": "500.00"},
    )

    assert response.status_code == 403


def test_create_payment_link_api_key_missing_scope_rejected(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    raw_key, _ = make_api_key(fake_client, merchant_id, scopes=["payment_links:read"])

    response = client.post(
        "/v1/payment-links",
        headers={"X-API-Key": raw_key, "Idempotency-Key": str(uuid.uuid4())},
        json={"merchant_id": str(merchant_id), "amount": "500.00"},
    )

    assert response.status_code == 403
    assert "payment_links:write" in response.json()["error"]["message"]


def test_get_payment_link_api_key_correct_scope_allowed(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    raw_key, _ = make_api_key(fake_client, merchant_id, scopes=["payment_links:write", "payment_links:read"])

    created = client.post(
        "/v1/payment-links",
        headers={"X-API-Key": raw_key, "Idempotency-Key": str(uuid.uuid4())},
        json={"merchant_id": str(merchant_id), "amount": "500.00"},
    ).json()["data"]

    response = client.get(f"/v1/payment-links/{created['id']}", headers={"X-API-Key": raw_key})

    assert response.status_code == 200, response.text


def test_developer_role_cannot_create_payment_link(fake_client):
    """DEVELOPER is scoped to api_keys only — not general merchant data."""
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    dev_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, dev_id, "DEVELOPER")

    response = client.post(
        "/v1/payment-links",
        headers={**auth_headers(dev_id), "Idempotency-Key": str(uuid.uuid4())},
        json={"merchant_id": str(merchant_id), "amount": "500.00"},
    )

    assert response.status_code == 403


def test_create_payment_link_requires_idempotency_key(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    admin_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, admin_id, "MERCHANT_ADMIN")

    response = client.post(
        "/v1/payment-links",
        headers=auth_headers(admin_id),
        json={"merchant_id": str(merchant_id), "amount": "500.00"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_create_payment_link_is_idempotent_on_retry(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    admin_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, admin_id, "MERCHANT_ADMIN")

    body = {"merchant_id": str(merchant_id), "amount": "750.00"}
    headers = {**auth_headers(admin_id), "Idempotency-Key": "create-retry-key"}

    first = client.post("/v1/payment-links", headers=headers, json=body)
    second = client.post("/v1/payment-links", headers=headers, json=body)

    assert first.status_code == second.status_code == 201
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    assert len(fake_client.table("payment_links")._table.rows) == 1


# --- get by id -----------------------------------------------------------------


def test_get_payment_link_by_id(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    admin_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, admin_id, "MERCHANT_ADMIN")
    link = _create_link(fake_client, merchant_id, admin_id)

    response = client.get(f"/v1/payment-links/{link['id']}", headers=auth_headers(admin_id))

    assert response.status_code == 200
    assert response.json()["data"]["id"] == link["id"]


def test_get_payment_link_not_found(fake_client):
    merchant = create_merchant(fake_client)
    admin_id = uuid.uuid4()
    make_merchant_member(fake_client, uuid.UUID(merchant["id"]), admin_id, "MERCHANT_ADMIN")

    response = client.get(f"/v1/payment-links/{uuid.uuid4()}", headers=auth_headers(admin_id))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_get_payment_link_from_another_merchant_is_forbidden(fake_client):
    owner_merchant = create_merchant(fake_client, contact_email="owner@example.com")
    owner_id = uuid.uuid4()
    make_merchant_member(fake_client, uuid.UUID(owner_merchant["id"]), owner_id, "MERCHANT_ADMIN")
    link = _create_link(fake_client, uuid.UUID(owner_merchant["id"]), owner_id)

    other_merchant = create_merchant(fake_client, contact_email="other@example.com")
    outsider_id = uuid.uuid4()
    make_merchant_member(fake_client, uuid.UUID(other_merchant["id"]), outsider_id, "MERCHANT_ADMIN")

    response = client.get(f"/v1/payment-links/{link['id']}", headers=auth_headers(outsider_id))

    assert response.status_code == 403


def test_super_admin_can_get_any_payment_link(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    admin_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, admin_id, "MERCHANT_ADMIN")
    link = _create_link(fake_client, merchant_id, admin_id)

    super_admin_id = uuid.uuid4()
    make_super_admin(fake_client, super_admin_id)

    response = client.get(f"/v1/payment-links/{link['id']}", headers=auth_headers(super_admin_id))

    assert response.status_code == 200


# --- expiry --------------------------------------------------------------------


def test_get_payment_link_reports_expired_after_expires_at_passes(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    admin_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, admin_id, "MERCHANT_ADMIN")
    link = _create_link(fake_client, merchant_id, admin_id)
    _expire(fake_client, link["id"])

    response = client.get(f"/v1/payment-links/{link['id']}", headers=auth_headers(admin_id))

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "EXPIRED"
    # Persisted, not just computed for this one response.
    assert _row(fake_client, link["id"])["status"] == "EXPIRED"


def test_public_lookup_returns_expired_state_when_expires_at_has_passed(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    admin_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, admin_id, "MERCHANT_ADMIN")
    link = _create_link(fake_client, merchant_id, admin_id)
    _expire(fake_client, link["id"])

    response = client.get(f"/public/payment-links/{link['public_slug']}")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "EXPIRED"


def test_collect_prevented_on_expired_link(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    admin_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, admin_id, "MERCHANT_ADMIN")
    link = _create_link(fake_client, merchant_id, admin_id)
    _expire(fake_client, link["id"])

    response = client.post(
        f"/public/payment-links/{link['public_slug']}/collect",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"method": "STK_PUSH"},
    )

    assert response.status_code == 409
    assert "EXPIRED" in response.json()["error"]["message"]
    assert len(fake_client.table("collections")._table.rows) == 0


# --- cancellation --------------------------------------------------------------


def test_cancel_payment_link(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    admin_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, admin_id, "MERCHANT_ADMIN")
    link = _create_link(fake_client, merchant_id, admin_id)

    response = client.patch(f"/v1/payment-links/{link['id']}/cancel", headers=auth_headers(admin_id))

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "CANCELLED"


def test_cancel_is_idempotent_noop_on_repeat(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    admin_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, admin_id, "MERCHANT_ADMIN")
    link = _create_link(fake_client, merchant_id, admin_id)

    first = client.patch(f"/v1/payment-links/{link['id']}/cancel", headers=auth_headers(admin_id))
    second = client.patch(f"/v1/payment-links/{link['id']}/cancel", headers=auth_headers(admin_id))

    assert first.status_code == second.status_code == 200
    assert second.json()["data"]["status"] == "CANCELLED"
    cancel_events = [
        a for a in fake_client.table("audit_logs")._table.rows if a["action"] == "payment_link.cancelled"
    ]
    assert len(cancel_events) == 1  # the no-op retry didn't write a second entry


def test_cancel_paid_link_is_rejected(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    admin_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, admin_id, "MERCHANT_ADMIN")
    link = _create_link(fake_client, merchant_id, admin_id)
    _row(fake_client, link["id"])["status"] = "PAID"

    response = client.patch(f"/v1/payment-links/{link['id']}/cancel", headers=auth_headers(admin_id))

    assert response.status_code == 409


def test_collect_prevented_on_cancelled_link(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    admin_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, admin_id, "MERCHANT_ADMIN")
    link = _create_link(fake_client, merchant_id, admin_id)
    client.patch(f"/v1/payment-links/{link['id']}/cancel", headers=auth_headers(admin_id))

    response = client.post(
        f"/public/payment-links/{link['public_slug']}/collect",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"method": "STK_PUSH"},
    )

    assert response.status_code == 409
    assert "CANCELLED" in response.json()["error"]["message"]


def test_cancelled_link_is_not_publicly_payable_but_still_viewable(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    admin_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, admin_id, "MERCHANT_ADMIN")
    link = _create_link(fake_client, merchant_id, admin_id)
    client.patch(f"/v1/payment-links/{link['id']}/cancel", headers=auth_headers(admin_id))

    response = client.get(f"/public/payment-links/{link['public_slug']}")

    assert response.status_code == 200  # visible, so the checkout page can explain why it can't be paid
    assert response.json()["data"]["status"] == "CANCELLED"


# --- public lookup ---------------------------------------------------------


def test_public_lookup_of_active_link(fake_client):
    merchant = create_merchant(fake_client, business_name="Amina's Boutique")
    merchant_id = uuid.UUID(merchant["id"])
    admin_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, admin_id, "MERCHANT_ADMIN")
    link = _create_link(
        fake_client,
        merchant_id,
        admin_id,
        amount="1234.50",
        description="Order #7",
        customer_name="Baraka",
        customer_phone="+255700000000",
        expires_at="2099-01-01T00:00:00+00:00",
    )

    response = client.get(f"/public/payment-links/{link['public_slug']}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "ACTIVE"
    assert data["merchant_name"] == "Amina's Boutique"
    assert data["amount"] == "1234.50"
    assert data["currency"] == "TZS"
    assert data["description"] == "Order #7"
    assert data["customer_name"] == "Baraka"
    assert data["customer_phone"] == "+255700000000"
    assert data["expires_at"] is not None
    # No merchant-internal fields leak to the public view.
    assert "merchant_id" not in data
    assert "public_slug" not in data
    assert "id" not in data


def test_public_lookup_omits_customer_details_when_absent(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    admin_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, admin_id, "MERCHANT_ADMIN")
    link = _create_link(fake_client, merchant_id, admin_id)

    response = client.get(f"/public/payment-links/{link['public_slug']}")

    data = response.json()["data"]
    assert data["customer_name"] is None
    assert data["customer_phone"] is None
    assert data["expires_at"] is None


def test_public_lookup_unknown_slug_is_404(fake_client):
    response = client.get("/public/payment-links/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# --- successful collect, end to end ----------------------------------------


def test_collect_success_flow(fake_client):
    merchant = create_merchant(fake_client, webhook_url="https://merchant.example.com/webhooks")
    merchant_id = uuid.UUID(merchant["id"])
    admin_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, admin_id, "MERCHANT_ADMIN")
    link = _create_link(fake_client, merchant_id, admin_id, amount="1000.00")

    response = client.post(
        f"/public/payment-links/{link['public_slug']}/collect",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"method": "STK_PUSH", "customer_phone": "+255700000000"},
    )

    assert response.status_code == 202
    assert response.json()["data"]["status"] == "successful"
    assert _row(fake_client, link["id"])["status"] == "PAID"

    # No longer payable, but still publicly viewable as PAID.
    followup = client.get(f"/public/payment-links/{link['public_slug']}")
    assert followup.json()["data"]["status"] == "PAID"

    transactions = fake_client.table("transactions")._table.rows
    assert len(transactions) == 1
    assert Decimal(transactions[0]["net_amount"]) + Decimal(transactions[0]["fee_amount"]) == Decimal(
        transactions[0]["gross_amount"]
    )

    entries = [
        e
        for e in fake_client.table("ledger_entries")._table.rows
        if e["transaction_id"] == transactions[0]["id"]
    ]
    debits = sum(Decimal(e["amount"]) for e in entries if e["direction"] == "debit")
    credits = sum(Decimal(e["amount"]) for e in entries if e["direction"] == "credit")
    assert debits == credits

    events = fake_client.table("webhook_events")._table.rows
    assert any(e["event_name"] == "collection.success" for e in events)

    # paid_at is set (distinct from updated_at, which every write bumps).
    link_row = _row(fake_client, link["id"])
    assert link_row["paid_at"] is not None


def test_failure_reason_persisted_on_failed_collect(fake_client, monkeypatch):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    admin_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, admin_id, "MERCHANT_ADMIN")
    link = _create_link(fake_client, merchant_id, admin_id, amount="1000.00")

    monkeypatch.setenv("MOCK_PROVIDER_FAILURE_RATE", "1")
    get_settings.cache_clear()
    get_selcom_client.cache_clear()

    response = client.post(
        f"/public/payment-links/{link['public_slug']}/collect",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"method": "STK_PUSH", "customer_phone": "+255700000000"},
    )

    assert response.status_code == 202, response.text
    assert response.json()["data"]["status"] == "failed"

    collection_row = next(
        c for c in fake_client.table("collections")._table.rows if c["payment_link_id"] == link["id"]
    )
    assert collection_row["status"] == "failed"
    assert collection_row["failure_reason"]

    # A failed collect never marks the link paid.
    assert _row(fake_client, link["id"])["status"] == "ACTIVE"
    assert _row(fake_client, link["id"]).get("paid_at") is None


def test_collect_dynamic_qr_returns_qr_payload_and_stays_processing(fake_client):
    """Regression test: collect_payment_link() used to call execute_collection()
    for every method including DYNAMIC_QR, which never generates a QR at
    all. It must route DYNAMIC_QR through execute_dynamic_qr_collection()
    instead, return a real qr_payload, and leave both the collection and
    the payment link PROCESSING/ACTIVE — there's nothing to resolve
    synchronously for a QR nobody has scanned yet."""
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    admin_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, admin_id, "MERCHANT_ADMIN")
    link = _create_link(fake_client, merchant_id, admin_id, amount="2500.00")

    response = client.post(
        f"/public/payment-links/{link['public_slug']}/collect",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"method": "DYNAMIC_QR"},
    )

    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["status"] == "processing"
    assert data["qr_payload"]
    assert data["qr_expires_at"]
    assert data["expires_at"] == data["qr_expires_at"]

    assert _row(fake_client, link["id"])["status"] == "ACTIVE"
    assert fake_client.table("ledger_entries")._table.rows == []


def test_collect_rejects_disallowed_method(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    admin_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, admin_id, "MERCHANT_ADMIN")
    link = _create_link(fake_client, merchant_id, admin_id, allowed_payment_methods=["DYNAMIC_QR"])

    response = client.post(
        f"/public/payment-links/{link['public_slug']}/collect",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"method": "STK_PUSH"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_collect_is_idempotent_on_retry(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    admin_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, admin_id, "MERCHANT_ADMIN")
    link = _create_link(fake_client, merchant_id, admin_id, amount="250.00")

    body = {"method": "STK_PUSH"}
    headers = {"Idempotency-Key": "collect-retry-key"}

    first = client.post(f"/public/payment-links/{link['public_slug']}/collect", headers=headers, json=body)
    second = client.post(f"/public/payment-links/{link['public_slug']}/collect", headers=headers, json=body)

    assert first.status_code == second.status_code == 202
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    assert len(fake_client.table("collections")._table.rows) == 1
