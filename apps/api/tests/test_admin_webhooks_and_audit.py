"""GET /v1/admin/webhooks and /v1/admin/audit-logs — end to end against the
in-memory FakeSupabaseClient.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services.audit import write_audit_log
from app.services.webhooks import store_incoming_selcom_event
from tests.factories import TEST_JWT_SECRET, auth_headers, make_super_admin

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
    return admin_id, auth_headers(admin_id)


def test_list_admin_webhooks_requires_super_admin(fake_client):
    response = client.get("/v1/admin/webhooks", headers=auth_headers(uuid.uuid4()))
    assert response.status_code == 403


def test_list_admin_webhooks_reads_selcom_events(fake_client):
    store_incoming_selcom_event(
        fake_client,
        event_id="evt-123",
        event_type="collection.success",
        raw_body="{}",
        signature="sig",
        signature_valid=True,
    )
    _, headers = _admin_headers(fake_client)
    response = client.get("/v1/admin/webhooks", headers=headers)
    assert response.status_code == 200
    row = response.json()["data"][0]
    assert row["provider"] == "selcom"
    assert row["event_type"] == "collection.success"
    assert row["reference"] == "evt-123"
    assert row["status"] == "received"


def test_list_admin_webhooks_exposes_processing_error_for_reconciliation(fake_client):
    """The Webhooks page's "Unmatched Transactions" reconciliation metric
    is computed client-side from this field — has to actually be
    returned by the API, not silently dropped."""
    stored, _ = store_incoming_selcom_event(
        fake_client,
        event_id="evt-456",
        event_type="collection.success",
        raw_body="{}",
        signature="sig",
        signature_valid=True,
    )
    fake_client.table("selcom_webhook_events").update(
        {"status": "failed", "processing_error": "no matching collection for this transid/order_id"}
    ).eq("id", stored["id"]).execute()

    _, headers = _admin_headers(fake_client)
    response = client.get("/v1/admin/webhooks", headers=headers)
    row = response.json()["data"][0]
    assert row["processing_error"] == "no matching collection for this transid/order_id"


def test_list_admin_audit_logs_resolves_actor_name(fake_client):
    actor_id = uuid.uuid4()
    fake_client.seed_auth_user(actor_id, email="admin@example.com", full_name="Admin Person")
    write_audit_log(
        fake_client,
        actor_id=actor_id,
        action="merchant.status_updated",
        resource_type="merchant",
        resource_id=uuid.uuid4(),
        metadata={"status": "active"},
    )

    _, headers = _admin_headers(fake_client)
    response = client.get("/v1/admin/audit-logs", headers=headers)
    assert response.status_code == 200
    row = response.json()["data"][0]
    assert row["actor"] == "Admin Person"
    assert row["action"] == "merchant.status_updated"
    assert row["entity_type"] == "merchant"


def test_list_admin_audit_logs_actor_null_for_system_actions(fake_client):
    write_audit_log(
        fake_client,
        actor_id=None,
        actor_type="system",
        action="webhook.processed",
        resource_type="selcom_webhook_event",
    )

    _, headers = _admin_headers(fake_client)
    response = client.get("/v1/admin/audit-logs", headers=headers)
    assert response.status_code == 200
    row = response.json()["data"][0]
    assert row["actor"] is None
