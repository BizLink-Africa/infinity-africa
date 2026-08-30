"""Super Admin COLLECTION pricing-rule management —
/v1/admin/merchants/{id}/collection-pricing-rules and
/v1/admin/collection-pricing-rules/*. Mirrors test_admin_pricing.py (the
withdrawal-side sibling test file).
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from tests.factories import (
    TEST_JWT_SECRET,
    auth_headers,
    create_collection_pricing_rule,
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


def _merchant_id(fake_client) -> uuid.UUID:
    return uuid.UUID(create_merchant(fake_client)["id"])


def _admin(fake_client) -> uuid.UUID:
    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)
    return admin_id


def test_create_merchant_collection_pricing_rule(fake_client):
    merchant_id = _merchant_id(fake_client)
    admin_id = _admin(fake_client)

    response = client.post(
        f"/v1/admin/merchants/{merchant_id}/collection-pricing-rules",
        headers=auth_headers(admin_id),
        json={
            "channel": "HOSTED_CHECKOUT",
            "percentage_fee": "0.8",
            "flat_fee": "0",
            "minimum_fee": "50",
            "maximum_fee": "5000",
            "label": "Negotiated rate",
            "notes": "Contract #2026-114, signed 2026-08-30",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["merchant_id"] == str(merchant_id)
    assert body["channel"] == "HOSTED_CHECKOUT"
    assert body["percentage_fee"] == "0.800" or body["percentage_fee"] == "0.8"
    assert body["label"] == "Negotiated rate"
    assert body["notes"] == "Contract #2026-114, signed 2026-08-30"
    assert body["is_active"] is True


def test_create_rule_for_unknown_merchant_404s(fake_client):
    admin_id = _admin(fake_client)

    response = client.post(
        f"/v1/admin/merchants/{uuid.uuid4()}/collection-pricing-rules",
        headers=auth_headers(admin_id),
        json={"percentage_fee": "0.8"},
    )
    assert response.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"percentage_fee": "150"},  # over 100%
        {"minimum_fee": "5000", "maximum_fee": "1000"},  # max < min
        {"channel": "NOT_A_CHANNEL"},
    ],
)
def test_create_rule_validation_errors(fake_client, payload):
    merchant_id = _merchant_id(fake_client)
    admin_id = _admin(fake_client)

    response = client.post(
        f"/v1/admin/merchants/{merchant_id}/collection-pricing-rules", headers=auth_headers(admin_id), json=payload
    )
    assert response.status_code == 422


def test_no_business_specific_range_is_hardcoded(fake_client):
    """Explicitly not limited to a 0.4%-2.0% business range — a rate
    outside that (but still a sane percentage) must be accepted."""
    merchant_id = _merchant_id(fake_client)
    admin_id = _admin(fake_client)

    response = client.post(
        f"/v1/admin/merchants/{merchant_id}/collection-pricing-rules",
        headers=auth_headers(admin_id),
        json={"percentage_fee": "3.5"},
    )
    assert response.status_code == 200, response.text


def test_list_merchant_collection_pricing_rules(fake_client):
    merchant_id = _merchant_id(fake_client)
    admin_id = _admin(fake_client)
    create_collection_pricing_rule(fake_client, merchant_id=merchant_id, label="rule-a")
    create_collection_pricing_rule(fake_client, merchant_id=merchant_id, channel="DYNAMIC_QR", label="rule-b")

    response = client.get(
        f"/v1/admin/merchants/{merchant_id}/collection-pricing-rules", headers=auth_headers(admin_id)
    )

    assert response.status_code == 200
    labels = {row["label"] for row in response.json()["data"]}
    assert labels == {"rule-a", "rule-b"}


def test_update_collection_pricing_rule(fake_client):
    merchant_id = _merchant_id(fake_client)
    admin_id = _admin(fake_client)
    rule = create_collection_pricing_rule(fake_client, merchant_id=merchant_id, percentage_fee="0.4")

    response = client.patch(
        f"/v1/admin/collection-pricing-rules/{rule['id']}",
        headers=auth_headers(admin_id),
        json={"percentage_fee": "0.8"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["percentage_fee"] in ("0.800", "0.8")


def test_deactivate_and_reactivate_collection_pricing_rule(fake_client):
    merchant_id = _merchant_id(fake_client)
    admin_id = _admin(fake_client)
    rule = create_collection_pricing_rule(fake_client, merchant_id=merchant_id)

    deactivated = client.post(
        f"/v1/admin/collection-pricing-rules/{rule['id']}/deactivate", headers=auth_headers(admin_id)
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["data"]["is_active"] is False

    reactivated = client.post(
        f"/v1/admin/collection-pricing-rules/{rule['id']}/activate", headers=auth_headers(admin_id)
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["data"]["is_active"] is True


def test_platform_fallback_rule_create_and_list(fake_client):
    admin_id = _admin(fake_client)

    created = client.post(
        "/v1/admin/collection-pricing-rules/platform-fallback",
        headers=auth_headers(admin_id),
        json={"percentage_fee": "0.8", "label": "platform default"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["merchant_id"] is None

    listed = client.get("/v1/admin/collection-pricing-rules", headers=auth_headers(admin_id))
    assert listed.status_code == 200
    assert any(row["label"] == "platform default" for row in listed.json()["data"])


def test_non_super_admin_cannot_manage_collection_pricing_rules(fake_client):
    """Merchant cannot edit or override collection pricing — there's no
    merchant-authenticated route for this at all; a non-super-admin
    caller is rejected outright."""
    merchant_id = _merchant_id(fake_client)
    non_admin_id = uuid.uuid4()

    response = client.post(
        f"/v1/admin/merchants/{merchant_id}/collection-pricing-rules",
        headers=auth_headers(non_admin_id),
        json={"percentage_fee": "0.8"},
    )
    assert response.status_code == 403


# --- audit logging --------------------------------------------------------------


def test_create_update_deactivate_activate_are_all_audit_logged(fake_client):
    merchant_id = _merchant_id(fake_client)
    admin_id = _admin(fake_client)

    created = client.post(
        f"/v1/admin/merchants/{merchant_id}/collection-pricing-rules",
        headers=auth_headers(admin_id),
        json={"percentage_fee": "0.8"},
    ).json()["data"]
    client.patch(
        f"/v1/admin/collection-pricing-rules/{created['id']}",
        headers=auth_headers(admin_id),
        json={"percentage_fee": "1.0"},
    )
    client.post(f"/v1/admin/collection-pricing-rules/{created['id']}/deactivate", headers=auth_headers(admin_id))
    client.post(f"/v1/admin/collection-pricing-rules/{created['id']}/activate", headers=auth_headers(admin_id))

    actions = [a["action"] for a in fake_client.table("audit_logs")._table.rows]
    assert actions.count("collection_pricing_rule.created") == 1
    assert actions.count("collection_pricing_rule.updated") == 1
    assert actions.count("collection_pricing_rule.deactivated") == 1
    assert actions.count("collection_pricing_rule.activated") == 1

    create_event = next(a for a in fake_client.table("audit_logs")._table.rows if a["action"] == "collection_pricing_rule.created")
    assert create_event["actor_id"] == str(admin_id)
    assert create_event["merchant_id"] == str(merchant_id)


# --- rate limiting -------------------------------------------------------------


def test_write_endpoint_is_rate_limited(fake_client):
    from app.core.rate_limit import _limiter

    merchant_id = _merchant_id(fake_client)
    admin_id = _admin(fake_client)
    for _ in range(30):
        _limiter.check("collection_pricing_manage:testclient", limit=30, window_seconds=60)

    response = client.post(
        f"/v1/admin/merchants/{merchant_id}/collection-pricing-rules",
        headers=auth_headers(admin_id),
        json={"percentage_fee": "0.8"},
    )
    assert response.status_code == 429
