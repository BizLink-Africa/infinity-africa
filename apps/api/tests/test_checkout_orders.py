"""POST /v1/merchant/collections/create-order-minimal — Selcom Checkout's
Create Order - Minimal (https://developers.selcommobile.com/#create-order-minimal),
Step 1 for STK/USSD/wallet push, payment-link checkout, and dynamic
QR/token display. Exercises app/services/checkout_orders.py and the
router end to end against the in-memory FakeSupabaseClient, same pattern
as test_merchant_portal.py. The real Selcom client
(app.services.selcom_checkout.client.SelcomCheckoutHTTPClient) is
monkeypatched out — this file never makes a network call.
"""

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services.selcom_checkout.schemas import CreateOrderMinimalResult
from tests.factories import (
    TEST_JWT_SECRET,
    auth_headers,
    create_merchant,
    make_merchant_member,
)

client = TestClient(app)

REAL_SUCCESS_RESPONSE = {
    "reference": "0289999288",
    "resultcode": "000",
    "result": "SUCCESS",
    "message": "Payment notification logged",
    "data": [
        {
            "gateway_buyer_uuid": "12344321",
            "payment_token": "80008000",
            "qr": "QR",
            "payment_gateway_url": "aHR0cDpleGFtcGxlLmNvbS9wZy90MTIyMjI=",
        }
    ],
}

REAL_FAIL_RESPONSE = {
    "reference": "0289999289",
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
    """Stands in for SelcomCheckoutHTTPClient — captures the exact
    keyword arguments create_order_minimal() was called with, and returns
    a canned, already-parsed result instead of making a real HTTP call."""

    def __init__(self, *, credentials=None, response: dict = REAL_SUCCESS_RESPONSE):
        self.calls: list[dict] = []
        self._response = response

    async def create_order_minimal(self, **kwargs) -> CreateOrderMinimalResult:
        self.calls.append(kwargs)
        from app.services.selcom_checkout.parsing import (
            parse_create_order_minimal_response,
        )

        return parse_create_order_minimal_response(self._response)


def _patch_checkout_client(monkeypatch, fake, *, response: dict = REAL_SUCCESS_RESPONSE):
    import app.services.checkout_orders as checkout_orders_module

    instance = _FakeSelcomCheckoutClient(response=response)
    monkeypatch.setattr(checkout_orders_module, "SelcomCheckoutHTTPClient", lambda **kwargs: instance)
    return instance


def _payload(**overrides) -> dict:
    body = {
        "buyer_email": "john@example.com",
        "buyer_name": "John Joh",
        "buyer_phone": "+255682000000",
        "amount": "8000",
        "currency": "TZS",
        "no_of_items": 1,
    }
    body.update(overrides)
    return body


# --- happy path ------------------------------------------------------------------


def test_create_order_minimal_returns_parsed_fields(fake_client, monkeypatch):
    merchant_id, user_id = _merchant_and_member(fake_client)
    fake = _patch_checkout_client(monkeypatch, fake_client)

    response = client.post(
        "/v1/merchant/collections/create-order-minimal",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json=_payload(),
    )

    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["merchant_id"] == str(merchant_id)
    assert data["status"] == "created"
    assert data["gateway_buyer_uuid"] == "12344321"
    assert data["payment_token"] == "80008000"
    assert data["qr"] == "QR"
    assert data["payment_gateway_url"] == "http:example.com/pg/t12222"
    assert data["provider_reference"] == "0289999288"
    assert data["provider_result_code"] == "000"
    assert data["provider_result"] == "SUCCESS"
    assert data["order_id"].startswith("ORD-")
    # order_id is server-generated, never taken from the request body.
    assert "order_id" not in _payload()

    assert len(fake.calls) == 1


def test_buyer_phone_is_normalized_before_reaching_selcom(fake_client, monkeypatch):
    _merchant_id, user_id = _merchant_and_member(fake_client)
    fake = _patch_checkout_client(monkeypatch, fake_client)

    response = client.post(
        "/v1/merchant/collections/create-order-minimal",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json=_payload(buyer_phone="+255 682 000 000"),
    )

    assert response.status_code == 202, response.text
    assert fake.calls[0]["buyer_phone"] == "255682000000"


def test_optional_fields_omitted_when_not_provided(fake_client, monkeypatch):
    _merchant_id, user_id = _merchant_and_member(fake_client)
    fake = _patch_checkout_client(monkeypatch, fake_client)

    response = client.post(
        "/v1/merchant/collections/create-order-minimal",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json=_payload(),
    )

    assert response.status_code == 202, response.text
    call = fake.calls[0]
    assert call.get("buyer_remarks") is None
    assert call.get("merchant_remarks") is None


def test_never_calls_wallet_payment():
    """Static guarantee, not a runtime assertion: the router/service for
    this endpoint imports nothing named wallet-payment-shaped, and
    _FakeSelcomCheckoutClient above only defines create_order_minimal —
    if the implementation ever called anything else on the client, this
    whole test module would fail with AttributeError, not silently pass."""
    import inspect

    import app.services.checkout_orders as checkout_orders_module

    source = inspect.getsource(checkout_orders_module)
    assert "wallet_payment" not in source
    assert "process_wallet" not in source


# --- failure from Selcom (order rejected, not a transport error) -----------------


def test_selcom_rejection_is_still_stored_and_returns_202(fake_client, monkeypatch):
    """A 202 here means "the order attempt was recorded", not "payment
    succeeded" — check `status` in the body, same convention as the
    push-collection endpoints. Mirrors disbursements.py always keeping
    the raw provider response regardless of outcome."""
    _merchant_id, user_id = _merchant_and_member(fake_client)
    _patch_checkout_client(monkeypatch, fake_client, response=REAL_FAIL_RESPONSE)

    response = client.post(
        "/v1/merchant/collections/create-order-minimal",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json=_payload(),
    )

    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["status"] == "failed"
    assert data["provider_result"] == "FAIL"
    assert data["provider_message"] == "Invalid order"


# --- idempotency -------------------------------------------------------------------


def test_retried_request_with_same_idempotency_key_does_not_call_selcom_twice(fake_client, monkeypatch):
    _merchant_id, user_id = _merchant_and_member(fake_client)
    fake = _patch_checkout_client(monkeypatch, fake_client)
    key = _idem()

    first = client.post(
        "/v1/merchant/collections/create-order-minimal",
        headers={**auth_headers(user_id), "Idempotency-Key": key},
        json=_payload(),
    )
    second = client.post(
        "/v1/merchant/collections/create-order-minimal",
        headers={**auth_headers(user_id), "Idempotency-Key": key},
        json=_payload(),
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    assert len(fake.calls) == 1


def test_role_gating_matches_withdrawals_admin_and_staff_allowed(fake_client, monkeypatch):
    _merchant_id, user_id = _merchant_and_member(fake_client, role="MERCHANT_STAFF")
    _patch_checkout_client(monkeypatch, fake_client)

    response = client.post(
        "/v1/merchant/collections/create-order-minimal",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json=_payload(),
    )

    assert response.status_code == 202, response.text


# --- payment link validation -------------------------------------------------------


def test_rejects_payment_link_from_another_merchant(fake_client, monkeypatch):
    _other_merchant_id, other_user_id = _merchant_and_member(fake_client)
    _merchant_id, user_id = _merchant_and_member(fake_client)
    _patch_checkout_client(monkeypatch, fake_client)

    link = client.post(
        "/v1/merchant/payment-links",
        headers={**auth_headers(other_user_id), "Idempotency-Key": _idem()},
        json={"amount": "1000", "currency": "TZS"},
    ).json()["data"]

    response = client.post(
        "/v1/merchant/collections/create-order-minimal",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json=_payload(payment_link_id=link["id"]),
    )

    assert response.status_code == 422


def test_rejects_expired_payment_link(fake_client, monkeypatch):
    """Same regression class as
    test_self_service_collection_rejects_expired_payment_link in
    test_merchant_portal.py, for this new endpoint."""
    _merchant_id, user_id = _merchant_and_member(fake_client)
    _patch_checkout_client(monkeypatch, fake_client)

    link = client.post(
        "/v1/merchant/payment-links",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={"amount": "1000", "currency": "TZS"},
    ).json()["data"]
    fake_client.table("payment_links")._table.rows[0]["status"] = "EXPIRED"

    response = client.post(
        "/v1/merchant/collections/create-order-minimal",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json=_payload(payment_link_id=link["id"]),
    )

    assert response.status_code == 409
    assert len(fake_client.table("checkout_orders")._table.rows) == 0


def test_does_not_reject_payment_link_missing_from_stk_push_allowed_methods(fake_client, monkeypatch):
    """Regression guard: create-order-minimal must NOT reuse
    validate_payment_link_for_collection(method=STK_PUSH) wholesale — a
    payment link that only allows DYNAMIC_QR must still be accepted here,
    since this endpoint doesn't commit to any specific method yet."""
    _merchant_id, user_id = _merchant_and_member(fake_client)
    _patch_checkout_client(monkeypatch, fake_client)

    link = client.post(
        "/v1/merchant/payment-links",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json={"amount": "1000", "currency": "TZS", "allowed_payment_methods": ["DYNAMIC_QR"]},
    ).json()["data"]

    response = client.post(
        "/v1/merchant/collections/create-order-minimal",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json=_payload(payment_link_id=link["id"]),
    )

    assert response.status_code == 202, response.text


# --- DB storage --------------------------------------------------------------------


def test_raw_response_and_amount_stored_in_checkout_orders(fake_client, monkeypatch):
    _merchant_id, user_id = _merchant_and_member(fake_client)
    _patch_checkout_client(monkeypatch, fake_client)

    client.post(
        "/v1/merchant/collections/create-order-minimal",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json=_payload(amount="8000"),
    )

    rows = fake_client.table("checkout_orders")._table.rows
    assert len(rows) == 1
    assert Decimal(str(rows[0]["amount"])) == Decimal(8000)
    assert rows[0]["raw_response"] == REAL_SUCCESS_RESPONSE
    assert rows[0]["provider"] == "selcom"
