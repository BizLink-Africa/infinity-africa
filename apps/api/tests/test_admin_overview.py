"""GET /v1/admin/overview — end to end against the in-memory
FakeSupabaseClient, same pattern as test_admin_onboarding.py.
"""

import uuid
from datetime import datetime, timedelta, timezone

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


def test_overview_requires_super_admin(fake_client):
    response = client.get("/v1/admin/overview", headers=auth_headers(uuid.uuid4()))
    assert response.status_code == 403


def test_overview_counts_merchants_and_pending_onboarding(fake_client):
    create_merchant(fake_client)
    create_merchant(fake_client)
    merchant = create_merchant(fake_client)
    fake_client.seed(
        "onboarding_submissions",
        {
            "merchant_id": merchant["id"],
            "nature_of_business": "Retail",
            "business_category": "Retail",
            "physical_address": "Addr",
            "region_city": "Dar",
            "services_needed": [],
            "review_status": "PENDING_VERIFICATION",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)
    response = client.get("/v1/admin/overview", headers=auth_headers(admin_id))
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["total_merchants"] == 3
    assert body["pending_onboarding_requests"] == 1


def test_overview_platform_revenue_is_mtd_not_running_balance(fake_client):
    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)

    account = fake_client.seed(
        "ledger_accounts",
        {
            "merchant_id": None,
            "name": "Platform Revenue",
            "account_type": "revenue",
            "purpose": "platform_revenue",
            "currency": "TZS",
            "balance": "999999",  # all-time running balance — must NOT be what overview reports
        },
    )

    last_month = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
    this_month = datetime.now(timezone.utc).isoformat()

    fake_client.seed(
        "ledger_entries",
        {
            "transaction_id": str(uuid.uuid4()),
            "ledger_account_id": account["id"],
            "direction": "credit",
            "amount": "500",
            "currency": "TZS",
            "created_at": last_month,
        },
    )
    fake_client.seed(
        "ledger_entries",
        {
            "transaction_id": str(uuid.uuid4()),
            "ledger_account_id": account["id"],
            "direction": "credit",
            "amount": "700",
            "currency": "TZS",
            "created_at": this_month,
        },
    )

    response = client.get("/v1/admin/overview", headers=auth_headers(admin_id))
    assert response.status_code == 200
    assert response.json()["data"]["platform_revenue"] == "700.00" or float(
        response.json()["data"]["platform_revenue"]
    ) == 700
