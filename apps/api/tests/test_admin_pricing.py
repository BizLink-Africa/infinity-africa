"""Super Admin pricing-rule management — /v1/admin/merchants/{id}/pricing-rules
and /v1/admin/pricing-rules/*.
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
    create_pricing_rule,
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


def test_create_merchant_pricing_rule(fake_client):
    merchant_id = _merchant_id(fake_client)
    admin_id = _admin(fake_client)

    response = client.post(
        f"/v1/admin/merchants/{merchant_id}/pricing-rules",
        headers=auth_headers(admin_id),
        json={
            "channel": "MOBILE_MONEY",
            "percentage_fee": "1",
            "flat_fee": "500",
            "minimum_fee": "200",
            "maximum_fee": "5000",
            "processor_fee_flat": "300",
            "processor_fee_pass_through": True,
            "label": "Negotiated rate",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["merchant_id"] == str(merchant_id)
    assert body["channel"] == "MOBILE_MONEY"
    assert body["label"] == "Negotiated rate"
    assert body["is_active"] is True


def test_create_pricing_rule_for_unknown_merchant_404s(fake_client):
    admin_id = _admin(fake_client)

    response = client.post(
        f"/v1/admin/merchants/{uuid.uuid4()}/pricing-rules",
        headers=auth_headers(admin_id),
        json={"percentage_fee": "1"},
    )
    assert response.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"percentage_fee": "150"},  # over 100%
        {"minimum_fee": "5000", "maximum_fee": "1000"},  # max < min
        {"channel": "NOT_A_CHANNEL"},
        {"destination_code": "NOT_A_CODE"},
    ],
)
def test_create_pricing_rule_validation_errors(fake_client, payload):
    merchant_id = _merchant_id(fake_client)
    admin_id = _admin(fake_client)

    response = client.post(
        f"/v1/admin/merchants/{merchant_id}/pricing-rules", headers=auth_headers(admin_id), json=payload
    )
    assert response.status_code == 422


def test_list_merchant_pricing_rules(fake_client):
    merchant_id = _merchant_id(fake_client)
    admin_id = _admin(fake_client)
    create_pricing_rule(fake_client, merchant_id=merchant_id, label="rule-a")
    create_pricing_rule(fake_client, merchant_id=merchant_id, channel="BANK_ACCOUNT", label="rule-b")

    response = client.get(f"/v1/admin/merchants/{merchant_id}/pricing-rules", headers=auth_headers(admin_id))

    assert response.status_code == 200
    labels = {row["label"] for row in response.json()["data"]}
    assert labels == {"rule-a", "rule-b"}


def test_update_pricing_rule(fake_client):
    merchant_id = _merchant_id(fake_client)
    admin_id = _admin(fake_client)
    rule = create_pricing_rule(fake_client, merchant_id=merchant_id, flat_fee="500")

    response = client.patch(
        f"/v1/admin/pricing-rules/{rule['id']}", headers=auth_headers(admin_id), json={"flat_fee": "750"}
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["flat_fee"] == "750.00" or response.json()["data"]["flat_fee"] == "750"


def test_deactivate_pricing_rule(fake_client):
    merchant_id = _merchant_id(fake_client)
    admin_id = _admin(fake_client)
    rule = create_pricing_rule(fake_client, merchant_id=merchant_id)

    response = client.post(f"/v1/admin/pricing-rules/{rule['id']}/deactivate", headers=auth_headers(admin_id))

    assert response.status_code == 200
    assert response.json()["data"]["is_active"] is False


def test_platform_fallback_rule_create_and_list(fake_client):
    admin_id = _admin(fake_client)

    created = client.post(
        "/v1/admin/pricing-rules/platform-fallback",
        headers=auth_headers(admin_id),
        json={"flat_fee": "1000", "label": "platform default"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["merchant_id"] is None

    listed = client.get("/v1/admin/pricing-rules", headers=auth_headers(admin_id))
    assert listed.status_code == 200
    assert any(row["label"] == "platform default" for row in listed.json()["data"])


def test_non_super_admin_cannot_manage_pricing_rules(fake_client):
    merchant_id = _merchant_id(fake_client)
    non_admin_id = uuid.uuid4()

    response = client.post(
        f"/v1/admin/merchants/{merchant_id}/pricing-rules",
        headers=auth_headers(non_admin_id),
        json={"flat_fee": "500"},
    )
    assert response.status_code == 403
