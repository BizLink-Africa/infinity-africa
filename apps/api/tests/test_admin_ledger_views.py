"""GET /v1/admin/{payment-links,invoices,collections,withdrawals,transactions}
— smoke tests against the in-memory FakeSupabaseClient: one seeded row per
resource, assert 200 + correct field mapping + correct merchant_name join.
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


def test_list_admin_payment_links_requires_super_admin(fake_client):
    response = client.get("/v1/admin/payment-links", headers=auth_headers(uuid.uuid4()))
    assert response.status_code == 403


def test_list_admin_payment_links(fake_client):
    merchant = create_merchant(fake_client, business_name="Amani Store")
    fake_client.seed(
        "payment_links",
        {
            "merchant_id": merchant["id"],
            "amount": "10000",
            "currency": "TZS",
            "customer_name": "Baraka",
            "status": "ACTIVE",
            "allowed_payment_methods": ["USSD_PUSH"],
            "public_slug": "abc123",
            "public_url": "https://pay.infinity.test/abc123",
        },
    )
    response = client.get("/v1/admin/payment-links", headers=_admin_headers(fake_client))
    assert response.status_code == 200
    row = response.json()["data"][0]
    assert row["merchant_name"] == "Amani Store"
    assert row["customer_name"] == "Baraka"
    assert row["status"] == "ACTIVE"


def test_list_admin_invoices(fake_client):
    merchant = create_merchant(fake_client, business_name="Neema Salon")
    fake_client.seed(
        "invoices",
        {
            "merchant_id": merchant["id"],
            "invoice_number": "INV-1001",
            "customer_name": "Grace",
            "due_date": "2026-09-01",
            "currency": "TZS",
            "subtotal": "50000",
            "tax_amount": "0",
            "discount_amount": "0",
            "total_amount": "50000",
            "amount_paid": "0",
            "status": "SENT",
        },
    )
    response = client.get("/v1/admin/invoices", headers=_admin_headers(fake_client))
    assert response.status_code == 200
    row = response.json()["data"][0]
    assert row["merchant_name"] == "Neema Salon"
    assert row["invoice_number"] == "INV-1001"
    assert row["total_amount"] == "50000"


def test_list_admin_collections_uses_customer_phone_not_name(fake_client):
    merchant = create_merchant(fake_client, business_name="Juma Traders")
    fake_client.seed(
        "collections",
        {
            "merchant_id": merchant["id"],
            "method": "USSD_PUSH",
            "amount": "20000",
            "currency": "TZS",
            "customer_phone": "+255700000000",
            "provider_reference": "ref-1",
            "status": "successful",
            "initiated_at": "2026-08-16T00:00:00+00:00",
        },
    )
    response = client.get("/v1/admin/collections", headers=_admin_headers(fake_client))
    assert response.status_code == 200
    row = response.json()["data"][0]
    assert row["merchant_name"] == "Juma Traders"
    assert row["phone"] == "+255700000000"
    assert "customer_name" not in row


def test_list_admin_collections_can_be_filtered_by_merchant_and_source(fake_client):
    merchant_a = create_merchant(fake_client, business_name="Juma Traders")
    merchant_b = create_merchant(fake_client, business_name="Amani Store")
    fake_client.seed(
        "collections",
        {
            "merchant_id": merchant_a["id"],
            "method": "USSD_PUSH",
            "amount": "20000",
            "currency": "TZS",
            "source": "PAYMENT_LINK",
            "status": "successful",
            "initiated_at": "2026-08-16T00:00:00+00:00",
        },
    )
    fake_client.seed(
        "collections",
        {
            "merchant_id": merchant_a["id"],
            "method": "USSD_PUSH",
            "amount": "5000",
            "currency": "TZS",
            "source": "API_WALLET_PUSH",
            "status": "successful",
            "initiated_at": "2026-08-16T00:00:00+00:00",
        },
    )
    fake_client.seed(
        "collections",
        {
            "merchant_id": merchant_b["id"],
            "method": "USSD_PUSH",
            "amount": "9000",
            "currency": "TZS",
            "source": "PAYMENT_LINK",
            "status": "successful",
            "initiated_at": "2026-08-16T00:00:00+00:00",
        },
    )
    headers = _admin_headers(fake_client)

    by_merchant = client.get(f"/v1/admin/collections?merchant_id={merchant_a['id']}", headers=headers)
    assert by_merchant.status_code == 200
    assert {row["amount"] for row in by_merchant.json()["data"]} == {"20000", "5000"}

    by_source = client.get("/v1/admin/collections?source=API_WALLET_PUSH", headers=headers)
    assert by_source.status_code == 200
    rows = by_source.json()["data"]
    assert len(rows) == 1
    assert rows[0]["amount"] == "5000"

    combined = client.get(
        f"/v1/admin/collections?merchant_id={merchant_a['id']}&source=PAYMENT_LINK", headers=headers
    )
    assert combined.status_code == 200
    rows = combined.json()["data"]
    assert len(rows) == 1
    assert rows[0]["amount"] == "20000"


def test_list_admin_withdrawals_filters_pending_approval_queue(fake_client):
    merchant = create_merchant(fake_client, business_name="Baraka Textiles")
    fake_client.seed(
        "disbursements",
        {
            "merchant_id": merchant["id"],
            "method": "BANK_ACCOUNT",
            "amount": "620000",
            "currency": "TZS",
            "destination_name": "Baraka Ltd",
            "destination_identifier": "0123456789",
            "status": "SUCCESS",
            "requires_approval": False,
            "initiated_at": "2026-08-16T00:00:00+00:00",
        },
    )
    fake_client.seed(
        "disbursements",
        {
            "merchant_id": merchant["id"],
            "method": "SELCOM_PESA",
            "amount": "900000",
            "currency": "TZS",
            "destination_name": "Baraka Ltd",
            "destination_identifier": "0123456789",
            "status": "PENDING_ADMIN_APPROVAL",
            "requires_approval": True,
            "initiated_at": "2026-08-16T00:00:00+00:00",
        },
    )

    headers = _admin_headers(fake_client)
    all_rows = client.get("/v1/admin/withdrawals", headers=headers).json()["data"]
    assert len(all_rows) == 2

    queue = client.get(
        "/v1/admin/withdrawals",
        headers=headers,
        params={"status": "PENDING_ADMIN_APPROVAL", "requires_approval": True},
    ).json()["data"]
    assert len(queue) == 1
    assert queue[0]["status"] == "PENDING_ADMIN_APPROVAL"
    assert queue[0]["destination"] == "Baraka Ltd"


def test_list_admin_transactions(fake_client):
    merchant = create_merchant(fake_client, business_name="Kilimanjaro Cafe")
    fake_client.seed(
        "transactions",
        {
            "merchant_id": merchant["id"],
            "reference": "TXN-1",
            "type": "collection",
            "method": "USSD_PUSH",
            "gross_amount": "10000",
            "fee_amount": "200",
            "net_amount": "9800",
            "currency": "TZS",
            "status": "successful",
            "metadata": {},
        },
    )
    response = client.get("/v1/admin/transactions", headers=_admin_headers(fake_client))
    assert response.status_code == 200
    row = response.json()["data"][0]
    assert row["merchant_name"] == "Kilimanjaro Cafe"
    assert row["reference"] == "TXN-1"
    assert row["net_amount"] == "9800"
