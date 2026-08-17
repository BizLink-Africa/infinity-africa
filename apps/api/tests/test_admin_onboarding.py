"""Super-admin onboarding review — /v1/admin/onboarding/* — end to end
against the in-memory FakeSupabaseClient, same pattern as
test_merchant_portal.py / test_onboarding.py.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from tests.factories import TEST_JWT_SECRET, auth_headers, make_super_admin

client = TestClient(app)


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _valid_payload(**overrides) -> dict:
    return {
        "business_name": "Kilimanjaro Fresh Produce",
        "nature_of_business": "Agriculture",
        "business_category": "Wholesale",
        "physical_address": "Njiro Road",
        "region_city": "Arusha",
        "website_url": None,
        "contact_phone": "+255712345678",
        "services_needed": ["PAYMENT_COLLECTION"],
        "accepted_terms": True,
        "accepted_privacy": True,
        **overrides,
    }


def _submit_onboarding(user_id: uuid.UUID, **overrides) -> dict:
    response = client.post(
        "/v1/onboarding/merchant-account", headers=auth_headers(user_id), json=_valid_payload(**overrides)
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_list_requires_super_admin(fake_client):
    _submit_onboarding(uuid.uuid4())
    response = client.get("/v1/admin/onboarding", headers=auth_headers(uuid.uuid4()))
    assert response.status_code == 403


def test_list_returns_submitted_merchant(fake_client):
    _submit_onboarding(uuid.uuid4())
    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)

    response = client.get("/v1/admin/onboarding", headers=auth_headers(admin_id))
    assert response.status_code == 200
    rows = response.json()["data"]
    assert len(rows) == 1
    row = rows[0]
    assert row["business_name"] == "Kilimanjaro Fresh Produce"
    assert row["owner_email"] == "user@example.com"
    assert row["contact_phone"] == "255712345678"  # normalized, no leading +
    assert row["nature_of_business"] == "Agriculture"
    assert row["physical_address"] == "Njiro Road"
    assert row["services_needed"] == ["PAYMENT_COLLECTION"]
    assert row["document_status"] == "UPLOADED"  # no documents uploaded yet -> treated as incomplete/pending
    assert row["review_status"] == "PENDING_VERIFICATION"


def test_get_detail_includes_signed_urls_for_documents(fake_client):
    submitted = _submit_onboarding(uuid.uuid4())
    merchant_id = submitted["merchant"]["id"]
    fake_client.seed(
        "onboarding_documents",
        {
            "merchant_id": merchant_id,
            "document_type": "NIDA",
            "file_path": f"{merchant_id}/NIDA.pdf",
            "original_filename": "nida.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 100,
            "upload_status": "UPLOADED",
            "uploaded_by": str(uuid.uuid4()),
            "uploaded_at": "2026-08-15T00:00:00+00:00",
        },
    )
    submission_id = next(
        r["id"] for r in fake_client.table("onboarding_submissions")._table.rows if r["merchant_id"] == merchant_id
    )

    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)
    response = client.get(f"/v1/admin/onboarding/{submission_id}", headers=auth_headers(admin_id))
    assert response.status_code == 200
    body = response.json()["data"]
    assert len(body["documents"]) == 1
    assert body["documents"][0]["signed_url"] is not None
    assert body["documents"][0]["signed_url"].startswith("https://fake.storage.test/")


def test_approve_promotes_merchant_status(fake_client):
    submitted = _submit_onboarding(uuid.uuid4())
    merchant_id = submitted["merchant"]["id"]
    submission_id = next(
        r["id"] for r in fake_client.table("onboarding_submissions")._table.rows if r["merchant_id"] == merchant_id
    )

    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)
    response = client.post(f"/v1/admin/onboarding/{submission_id}/approve", headers=auth_headers(admin_id))
    assert response.status_code == 200
    assert response.json()["data"]["review_status"] == "VERIFIED"

    merchant = next(r for r in fake_client.table("merchants")._table.rows if r["id"] == merchant_id)
    assert merchant["status"] == "active"
    assert merchant["kyc_status"] == "verified"


def test_reject_sets_status_and_note_without_touching_merchant(fake_client):
    submitted = _submit_onboarding(uuid.uuid4())
    merchant_id = submitted["merchant"]["id"]
    submission_id = next(
        r["id"] for r in fake_client.table("onboarding_submissions")._table.rows if r["merchant_id"] == merchant_id
    )

    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)
    response = client.post(
        f"/v1/admin/onboarding/{submission_id}/reject",
        headers=auth_headers(admin_id),
        json={"review_note": "Business licence photo is unreadable"},
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["review_status"] == "REJECTED"
    assert body["review_note"] == "Business licence photo is unreadable"

    merchant = next(r for r in fake_client.table("merchants")._table.rows if r["id"] == merchant_id)
    assert merchant["status"] == "pending"  # untouched by reject
    assert merchant["kyc_status"] == "unverified"


def test_request_more_info(fake_client):
    submitted = _submit_onboarding(uuid.uuid4())
    merchant_id = submitted["merchant"]["id"]
    submission_id = next(
        r["id"] for r in fake_client.table("onboarding_submissions")._table.rows if r["merchant_id"] == merchant_id
    )

    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)
    response = client.post(
        f"/v1/admin/onboarding/{submission_id}/request-more-info",
        headers=auth_headers(admin_id),
        json={"review_note": "Please upload a clearer TIN certificate"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["review_status"] == "INFO_REQUESTED"


def test_rejected_merchant_can_resubmit_and_reappears_pending(fake_client):
    user_id = uuid.uuid4()
    submitted = _submit_onboarding(user_id)
    merchant_id = submitted["merchant"]["id"]
    submission_id = next(
        r["id"] for r in fake_client.table("onboarding_submissions")._table.rows if r["merchant_id"] == merchant_id
    )

    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)
    client.post(f"/v1/admin/onboarding/{submission_id}/reject", headers=auth_headers(admin_id), json={})

    status_response = client.get("/v1/onboarding/status", headers=auth_headers(user_id))
    assert status_response.json()["data"]["next_path"] == "/onboarding"

    resubmit = client.post(
        "/v1/onboarding/merchant-account", headers=auth_headers(user_id), json=_valid_payload()
    )
    assert resubmit.status_code == 201

    status_after = client.get("/v1/onboarding/status", headers=auth_headers(user_id))
    assert status_after.json()["data"]["account_status"] == "PENDING_VERIFICATION"


# --- PATCH .../{merchant_id}/approve|reject|request-more-info ---------------


def test_approve_by_merchant_id(fake_client):
    submitted = _submit_onboarding(uuid.uuid4())
    merchant_id = submitted["merchant"]["id"]

    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)
    response = client.patch(f"/v1/admin/onboarding/{merchant_id}/approve", headers=auth_headers(admin_id))
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["review_status"] == "VERIFIED"
    assert body["merchant_id"] == merchant_id

    merchant = next(r for r in fake_client.table("merchants")._table.rows if r["id"] == merchant_id)
    assert merchant["status"] == "active"


def test_reject_by_merchant_id(fake_client):
    submitted = _submit_onboarding(uuid.uuid4())
    merchant_id = submitted["merchant"]["id"]

    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)
    response = client.patch(
        f"/v1/admin/onboarding/{merchant_id}/reject",
        headers=auth_headers(admin_id),
        json={"review_note": "Unreadable licence"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["review_status"] == "REJECTED"


def test_patch_by_id_404_when_no_submission_for_merchant(fake_client):
    admin_id = uuid.uuid4()
    make_super_admin(fake_client, admin_id)
    response = client.patch(f"/v1/admin/onboarding/{uuid.uuid4()}/approve", headers=auth_headers(admin_id))
    assert response.status_code == 404
