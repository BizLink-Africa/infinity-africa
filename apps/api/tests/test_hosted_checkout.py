"""Selcom hosted checkout (2026-08-23) — Infinity no longer asks a
merchant or customer to pick a channel; every collection now always
redirects to Selcom's own hosted checkout page via create-order-minimal.
Covers both entry points:

- POST /v1/merchant/collections/hosted-checkout ("Request Collection")
- POST /public/payment-links/{slug}/pay/checkout ("Pay securely")

Exercises app/services/hosted_checkout.py end to end against the
in-memory FakeSupabaseClient. The real Selcom client is monkeypatched
out — this file never makes a network call.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services.selcom_checkout.parsing import parse_create_order_minimal_response
from tests.factories import (
    TEST_JWT_SECRET,
    auth_headers,
    create_merchant,
    make_merchant_member,
)

client = TestClient(app)

REAL_SUCCESS_RESPONSE = {
    "reference": "S20690700000",
    "resultcode": "000",
    "result": "SUCCESS",
    "message": "Payment notification logged",
    "data": [
        {
            "payment_token": "80008000",
            "qr": "000201...",
            "payment_gateway_url": "aHR0cHM6Ly90emEuc2VsY29tLm9ubGluZS9wYXltZW50Z3cvY2hlY2tvdXQvVEVTVA==",
        }
    ],
}

REAL_FAIL_RESPONSE = {
    "reference": "S20690700001",
    "resultcode": "651",
    "result": "FAIL",
    "message": "Invalid order",
}


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("SELCOM_CHECKOUT_BASE_URL", "https://checkout.example.selcommobile.com")
    monkeypatch.setenv("SELCOM_CHECKOUT_API_KEY", "test-key")
    monkeypatch.setenv("SELCOM_CHECKOUT_API_SECRET", "test-secret")
    monkeypatch.setenv("SELCOM_CHECKOUT_VENDOR", "VENDORTEST")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _idem() -> str:
    return uuid.uuid4().hex


def _merchant_and_member(fake_client, role: str = "MERCHANT_ADMIN"):
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    user_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, user_id, role)
    return merchant_id, user_id


class _FakeSelcomCheckoutClient:
    def __init__(self, *, credentials=None, response: dict = REAL_SUCCESS_RESPONSE):
        self.calls: list[dict] = []
        self._response = response

    async def create_order_minimal(self, **kwargs):
        self.calls.append(kwargs)
        return parse_create_order_minimal_response(self._response)


def _patch_checkout_client(monkeypatch, *, response: dict = REAL_SUCCESS_RESPONSE):
    import app.services.checkout_orders as checkout_orders_module

    instance = _FakeSelcomCheckoutClient(response=response)
    monkeypatch.setattr(checkout_orders_module, "SelcomCheckoutHTTPClient", lambda **kwargs: instance)
    return instance


# --- Merchant Portal "Request Collection" -------------------------------------------


def test_hosted_checkout_collection_accepts_request_without_channel(fake_client, monkeypatch):
    """No `method` field anywhere in the request — this is the whole
    point of task 4: channel/payment_method is no longer required."""
    merchant_id, user_id = _merchant_and_member(fake_client)
    _patch_checkout_client(monkeypatch)

    response = client.post(
        "/v1/merchant/collections/hosted-checkout",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={"customer_name": "Grace", "amount": "5000", "description": "Order #1"},
    )

    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["method"] == "HOSTED_CHECKOUT"
    assert data["merchant_id"] == str(merchant_id)
    assert data["status"] == "processing"


def test_hosted_checkout_collection_creates_order_via_create_order_minimal(fake_client, monkeypatch):
    merchant_id, user_id = _merchant_and_member(fake_client)
    fake = _patch_checkout_client(monkeypatch)

    response = client.post(
        "/v1/merchant/collections/hosted-checkout",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={"amount": "5000"},
    )

    assert response.status_code == 202, response.text
    assert len(fake.calls) == 1
    order_row = fake_client.table("checkout_orders")._table.rows[0]
    assert order_row["merchant_id"] == str(merchant_id)
    assert order_row["status"] == "created"


def test_hosted_checkout_collection_returns_decoded_payment_gateway_url(fake_client, monkeypatch):
    _merchant_id, user_id = _merchant_and_member(fake_client)
    _patch_checkout_client(monkeypatch)

    response = client.post(
        "/v1/merchant/collections/hosted-checkout",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={"amount": "5000"},
    )

    assert response.status_code == 202, response.text
    # Never the raw base64 Selcom returns — already decoded server-side.
    assert response.json()["data"]["payment_gateway_url"] == "https://tza.selcom.online/paymentgw/checkout/TEST"


def test_hosted_checkout_collection_works_without_customer_phone(fake_client, monkeypatch):
    """Task 1: "Customer phone if needed" — must not be required."""
    _merchant_id, user_id = _merchant_and_member(fake_client)
    fake = _patch_checkout_client(monkeypatch)

    response = client.post(
        "/v1/merchant/collections/hosted-checkout",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={"amount": "5000"},
    )

    assert response.status_code == 202, response.text
    # A placeholder must still have been sent to Selcom (its API requires
    # *a* buyer_phone) — but never the real customer_phone field, which
    # stays null since none was ever provided.
    assert fake.calls[0]["buyer_phone"]
    assert response.json()["data"]["customer_phone"] is None


def test_hosted_checkout_collection_failed_order_recorded_not_502(fake_client, monkeypatch):
    _merchant_id, user_id = _merchant_and_member(fake_client)
    _patch_checkout_client(monkeypatch, response=REAL_FAIL_RESPONSE)

    response = client.post(
        "/v1/merchant/collections/hosted-checkout",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={"amount": "5000"},
    )

    assert response.status_code == 202, response.text
    assert response.json()["data"]["status"] == "failed"


# --- Public "Pay securely" -----------------------------------------------------------


def _create_link(fake_client, merchant_id, user_id, **overrides) -> dict:
    body = {"merchant_id": str(merchant_id), "amount": "1000.00", "currency": "TZS", **overrides}
    response = client.post(
        "/v1/payment-links",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json=body,
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_pay_checkout_accepts_request_without_allowed_channels_on_the_link(fake_client, monkeypatch):
    """Payment-link creation no longer requires allowed_payment_methods
    either — omit it entirely and confirm /pay/checkout still works."""
    merchant_id, user_id = _merchant_and_member(fake_client)
    _patch_checkout_client(monkeypatch)

    link_response = client.post(
        "/v1/payment-links",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={"merchant_id": str(merchant_id), "amount": "2500.00"},
    )
    assert link_response.status_code == 201, link_response.text
    link = link_response.json()["data"]

    response = client.post(
        f"/public/payment-links/{link['public_slug']}/pay/checkout",
        headers={"Idempotency-Key": _idem()},
        json={"customer_phone": "255747730270"},
    )

    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["payment_gateway_url"] == "https://tza.selcom.online/paymentgw/checkout/TEST"


def test_pay_checkout_never_marks_link_paid_or_credits_ledger(fake_client, monkeypatch):
    merchant_id, user_id = _merchant_and_member(fake_client)
    _patch_checkout_client(monkeypatch)
    link = _create_link(fake_client, merchant_id, user_id)

    response = client.post(
        f"/public/payment-links/{link['public_slug']}/pay/checkout",
        headers={"Idempotency-Key": _idem()},
        json={"customer_phone": "255747730270"},
    )

    assert response.status_code == 202, response.text
    assert client.get(f"/v1/payment-links/{link['id']}", headers=auth_headers(user_id)).json()["data"]["status"] == "ACTIVE"
    assert fake_client.table("ledger_entries")._table.rows == []


def test_pay_checkout_creates_collection_with_linked_transaction(fake_client, monkeypatch):
    """resolve_collection() (called later by webhook/manual refresh) needs
    exactly one linked transaction to post ledger entries against."""
    merchant_id, user_id = _merchant_and_member(fake_client)
    _patch_checkout_client(monkeypatch)
    link = _create_link(fake_client, merchant_id, user_id)

    response = client.post(
        f"/public/payment-links/{link['public_slug']}/pay/checkout",
        headers={"Idempotency-Key": _idem()},
        json={"customer_phone": "255747730270"},
    )
    collection_id = response.json()["data"]["collection_id"]

    collection_row = next(c for c in fake_client.table("collections")._table.rows if c["id"] == collection_id)
    assert collection_row["method"] == "HOSTED_CHECKOUT"
    assert any(t["collection_id"] == collection_id for t in fake_client.table("transactions")._table.rows)


def test_pay_checkout_is_idempotent_beyond_the_idempotency_key(fake_client, monkeypatch):
    merchant_id, user_id = _merchant_and_member(fake_client)
    fake = _patch_checkout_client(monkeypatch)
    link = _create_link(fake_client, merchant_id, user_id)

    for _ in range(2):
        response = client.post(
            f"/public/payment-links/{link['public_slug']}/pay/checkout",
            headers={"Idempotency-Key": _idem()},
            json={"customer_phone": "255747730270"},
        )
        assert response.status_code == 202, response.text

    assert len(fake.calls) == 1


def test_pay_checkout_uses_placeholder_phone_when_link_and_request_both_lack_one(fake_client, monkeypatch):
    """Task 3: "Collect any missing required customer details" — but if
    the frontend still submits with nothing (e.g. link already had one
    that later got cleared), this must not 500."""
    merchant_id, user_id = _merchant_and_member(fake_client)
    fake = _patch_checkout_client(monkeypatch)
    link = _create_link(fake_client, merchant_id, user_id)

    response = client.post(
        f"/public/payment-links/{link['public_slug']}/pay/checkout",
        headers={"Idempotency-Key": _idem()},
        json={},
    )

    assert response.status_code == 202, response.text
    assert fake.calls[0]["buyer_phone"]


# --- Backward compatibility: old channel-based rows keep working ---------------------


def test_old_collections_with_legacy_method_still_readable(fake_client, monkeypatch):
    """Old USSD_PUSH/STK_PUSH/SELCOM_PESA_PUSH/DYNAMIC_QR rows must not
    crash anything now that HOSTED_CHECKOUT exists alongside them."""
    merchant_id, user_id = _merchant_and_member(fake_client)
    fake_client.seed(
        "collections",
        {
            "merchant_id": str(merchant_id),
            "method": "STK_PUSH",
            "amount": "1000.00",
            "currency": "TZS",
            "status": "successful",
            "provider": "selcom_checkout",
            "initiated_at": "2026-08-01T09:00:00Z",
        },
    )

    response = client.get("/v1/merchant/collections", headers=auth_headers(user_id))

    assert response.status_code == 200, response.text
    assert response.json()["data"][0]["method"] == "STK_PUSH"


def test_old_payment_link_with_legacy_allowed_methods_still_readable(fake_client, monkeypatch):
    merchant_id, user_id = _merchant_and_member(fake_client)
    link = _create_link(
        fake_client, merchant_id, user_id, allowed_payment_methods=["USSD_PUSH", "STK_PUSH"]
    )

    response = client.get(f"/v1/payment-links/{link['id']}", headers=auth_headers(user_id))

    assert response.status_code == 200, response.text
    assert response.json()["data"]["allowed_payment_methods"] == ["USSD_PUSH", "STK_PUSH"]


def test_new_payment_link_omits_allowed_payment_methods_and_gets_legacy_default(fake_client, monkeypatch):
    """The field is no longer collected from the merchant — confirms the
    backend default never accidentally includes HOSTED_CHECKOUT, which
    would violate payment_links' own CHECK constraint."""
    merchant_id, user_id = _merchant_and_member(fake_client)

    response = client.post(
        "/v1/payment-links",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={"merchant_id": str(merchant_id), "amount": "500.00"},
    )

    assert response.status_code == 201, response.text
    assert "HOSTED_CHECKOUT" not in response.json()["data"]["allowed_payment_methods"]


# --- No card-exclusion logic ----------------------------------------------------------


def test_no_card_exclusion_logic_exists():
    """Static guarantee, not a runtime assertion: a payment method
    disabled at the Selcom account level (confirmed: not card-enabled)
    needs no exclusion/filtering logic anywhere in this codebase —
    Selcom's hosted checkout page itself only ever shows what's enabled
    on the account. This module's own docstrings deliberately avoid
    naming that method so this check stays a simple, honest scan rather
    than an AST hack to skip over its own comments."""
    import inspect

    import app.services.hosted_checkout as hosted_checkout_module

    source = inspect.getsource(hosted_checkout_module)
    assert "card" not in source.lower()
