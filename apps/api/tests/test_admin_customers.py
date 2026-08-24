"""GET /v1/admin/customers — derived from real collections (grouped by
merchant_id + customer_phone), not read from the dormant, never-written
public.customers table. See app/services/admin_customers.py's own
docstring for why.
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
    make_super_admin,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _admin_headers(fake_client) -> dict:
    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)
    return auth_headers(admin_id)


def _seed_collection(fake_client, *, merchant_id, phone, amount="1000", status="successful", payment_link_id=None, created_at="2026-08-20T10:00:00+00:00", completed_at=None):
    return fake_client.seed(
        "collections",
        {
            "merchant_id": str(merchant_id),
            "customer_phone": phone,
            "payment_link_id": payment_link_id,
            "amount": amount,
            "currency": "TZS",
            "status": status,
            "method": "STK_PUSH",
            "created_at": created_at,
            "completed_at": completed_at or (created_at if status == "successful" else None),
            "source": "PAYMENT_LINK" if payment_link_id else "DASHBOARD_REQUEST",
        },
    )


def test_requires_super_admin(fake_client):
    response = client.get("/v1/admin/customers", headers=auth_headers(uuid.uuid4()))
    assert response.status_code == 403


def test_groups_collections_into_customers_by_merchant_and_phone(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    _seed_collection(fake_client, merchant_id=merchant_id, phone="255700000001", amount="1000")
    _seed_collection(fake_client, merchant_id=merchant_id, phone="255700000001", amount="2000")
    _seed_collection(fake_client, merchant_id=merchant_id, phone="255700000002", amount="500")

    response = client.get("/v1/admin/customers", headers=_admin_headers(fake_client))
    assert response.status_code == 200, response.text
    rows = response.json()["data"]
    assert len(rows) == 2

    repeat_customer = next(r for r in rows if r["phone"] == "255700000001")
    assert repeat_customer["transaction_count"] == 2
    assert repeat_customer["total_spent"] == "3000"

    one_off_customer = next(r for r in rows if r["phone"] == "255700000002")
    assert one_off_customer["transaction_count"] == 1
    assert one_off_customer["total_spent"] == "500"


def test_only_successful_collections_count_toward_total_spent(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    _seed_collection(fake_client, merchant_id=merchant_id, phone="255700000003", amount="1000", status="successful")
    _seed_collection(fake_client, merchant_id=merchant_id, phone="255700000003", amount="5000", status="failed")

    response = client.get("/v1/admin/customers", headers=_admin_headers(fake_client))
    row = response.json()["data"][0]
    assert row["total_spent"] == "1000"
    assert row["transaction_count"] == 2  # both attempts still count as activity


def test_enriches_name_from_the_linked_payment_link(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    link = fake_client.seed(
        "payment_links",
        {
            "merchant_id": str(merchant_id),
            "amount": "1000",
            "currency": "TZS",
            "public_slug": "abc123",
            "status": "PAID",
            "customer_name": "Grace Mushi",
            "customer_phone": "255700000004",
        },
    )
    _seed_collection(
        fake_client, merchant_id=merchant_id, phone="255700000004", payment_link_id=link["id"], amount="1000"
    )

    response = client.get("/v1/admin/customers", headers=_admin_headers(fake_client))
    row = response.json()["data"][0]
    assert row["full_name"] == "Grace Mushi"


def test_customer_with_no_linked_payment_link_has_no_fabricated_name(fake_client):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    _seed_collection(fake_client, merchant_id=merchant_id, phone="255700000005")

    response = client.get("/v1/admin/customers", headers=_admin_headers(fake_client))
    row = response.json()["data"][0]
    assert row["full_name"] is None


def test_filters_by_merchant(fake_client):
    merchant_a = create_merchant(fake_client)
    merchant_b = create_merchant(fake_client)
    _seed_collection(fake_client, merchant_id=uuid.UUID(merchant_a["id"]), phone="255700000006")
    _seed_collection(fake_client, merchant_id=uuid.UUID(merchant_b["id"]), phone="255700000007")

    response = client.get(f"/v1/admin/customers?merchant_id={merchant_a['id']}", headers=_admin_headers(fake_client))
    rows = response.json()["data"]
    assert len(rows) == 1
    assert rows[0]["phone"] == "255700000006"


def test_customers_from_different_merchants_are_never_merged_even_with_the_same_phone(fake_client):
    """public.customers is explicitly per-merchant, never shared across
    tenants — the same real-world phone number paying two different
    merchants must show up as two separate customer rows, not one."""
    merchant_a = create_merchant(fake_client)
    merchant_b = create_merchant(fake_client)
    _seed_collection(fake_client, merchant_id=uuid.UUID(merchant_a["id"]), phone="255700000008")
    _seed_collection(fake_client, merchant_id=uuid.UUID(merchant_b["id"]), phone="255700000008")

    response = client.get("/v1/admin/customers", headers=_admin_headers(fake_client))
    rows = response.json()["data"]
    assert len(rows) == 2
    assert {r["merchant_id"] for r in rows} == {merchant_a["id"], merchant_b["id"]}
