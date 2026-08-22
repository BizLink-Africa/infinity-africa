"""POST /public/payment-links/{public_slug}/pay/wallet-push — the Selcom
Checkout create-order-minimal -> wallet-payment flow for a customer
paying a public payment link. Exercises app/services/wallet_push.py and
app/services/checkout_orders.py end to end against the in-memory
FakeSupabaseClient. The real Selcom client
(app.services.selcom_checkout.client.SelcomCheckoutHTTPClient) is
monkeypatched out in both app.services.checkout_orders and
app.services.wallet_push (both import it directly) — this file never
makes a network call or sends a real push.
"""

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services.selcom_checkout.schemas import (
    CreateOrderMinimalResult,
    WalletPaymentResult,
)
from tests.factories import (
    TEST_JWT_SECRET,
    auth_headers,
    create_merchant,
    make_merchant_member,
)

client = TestClient(app)

CREATE_ORDER_SUCCESS_RESPONSE = {
    "reference": "S20690427372",
    "resultcode": "000",
    "result": "SUCCESS",
    "message": "Payment notification logged",
    "data": [{"payment_token": "63850827", "payment_gateway_url": "aHR0cHM6Ly9leGFtcGxlLmNvbS9wYXk=", "qr": "QRDATA"}],
}

CREATE_ORDER_FAILED_RESPONSE = {
    "reference": "",
    "resultcode": "651",
    "result": "FAIL",
    "message": "Invalid vendor",
    "data": [],
}

WALLET_PAYMENT_PENDING_RESPONSE = {
    "reference": "0289999288",
    "resultcode": "111",
    "result": "PENDING",
    "message": "Request in progress. You will receive a callback shortly.",
    "data": [],
}

WALLET_PAYMENT_FAILED_RESPONSE = {
    "reference": "0289999289",
    "resultcode": "651",
    "result": "FAIL",
    "message": "Insufficient funds",
    "data": [],
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


def _create_payment_link(user_id: uuid.UUID, **overrides) -> dict:
    body = {"amount": "1000", "currency": "TZS"}
    body.update(overrides)
    response = client.post(
        "/v1/merchant/payment-links",
        headers={**auth_headers(user_id), "Idempotency-Key": _idem()},
        json=body,
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


class _FakeSelcomCheckoutClient:
    """Stands in for SelcomCheckoutHTTPClient across both call sites
    (app.services.checkout_orders and app.services.wallet_push) —
    records every call, in order, so "create-order-minimal is called
    before wallet-payment" is a real, checkable assertion, not an
    assumption."""

    def __init__(
        self,
        *,
        credentials=None,
        order_response: dict = CREATE_ORDER_SUCCESS_RESPONSE,
        payment_response: dict = WALLET_PAYMENT_PENDING_RESPONSE,
    ):
        self.calls: list[tuple[str, dict]] = []
        self._order_response = order_response
        self._payment_response = payment_response

    async def create_order_minimal(self, **kwargs) -> CreateOrderMinimalResult:
        from app.services.selcom_checkout.parsing import (
            parse_create_order_minimal_response,
        )

        self.calls.append(("create_order_minimal", kwargs))
        return parse_create_order_minimal_response(self._order_response)

    async def process_wallet_payment(self, **kwargs) -> WalletPaymentResult:
        from app.services.selcom_checkout.parsing import parse_wallet_payment_response

        self.calls.append(("process_wallet_payment", kwargs))
        return parse_wallet_payment_response(self._payment_response)


def _patch_checkout_client(monkeypatch, *, order_response=CREATE_ORDER_SUCCESS_RESPONSE, payment_response=WALLET_PAYMENT_PENDING_RESPONSE):
    import app.services.checkout_orders as checkout_orders_module
    import app.services.wallet_push as wallet_push_module

    fake = _FakeSelcomCheckoutClient(order_response=order_response, payment_response=payment_response)
    monkeypatch.setattr(checkout_orders_module, "SelcomCheckoutHTTPClient", lambda **kwargs: fake)
    monkeypatch.setattr(wallet_push_module, "SelcomCheckoutHTTPClient", lambda **kwargs: fake)
    return fake


def _pay(public_slug: str, phone: str = "255747730270", idempotency_key: str | None = None):
    return client.post(
        f"/public/payment-links/{public_slug}/pay/wallet-push",
        headers={"Idempotency-Key": idempotency_key or _idem()},
        json={"customer_phone": phone},
    )


# --- happy path ----------------------------------------------------------------------


def test_wallet_push_returns_pending_and_creates_a_collection(fake_client, monkeypatch):
    _merchant_id, user_id = _merchant_and_member(fake_client)
    link = _create_payment_link(user_id)
    fake = _patch_checkout_client(monkeypatch)

    response = _pay(link["public_slug"])

    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["payment_status"] == "pending"
    assert "PIN" in data["message"]

    collections = fake_client.table("collections")._table.rows
    assert len(collections) == 1
    assert collections[0]["status"] == "processing"
    assert collections[0]["provider_resultcode"] == "111"
    assert collections[0]["provider_result"] == "PENDING"
    assert collections[0]["method"] == "STK_PUSH"

    orders = fake_client.table("checkout_orders")._table.rows
    assert len(orders) == 1
    assert orders[0]["status"] == "created"
    assert collections[0]["checkout_order_id"] == orders[0]["id"]

    assert len(fake.calls) == 2


def test_response_is_stored_safely_on_both_rows(fake_client, monkeypatch):
    """"response stored safely" — every field the task asks for lands
    somewhere queryable: order_id/payment_token/qr/payment_gateway_url on
    the linked checkout_orders row (from create-order-minimal), and
    transid/reference/result/resultcode/raw_response on the collections
    row (from wallet-payment) — not just implicitly present in a log
    line."""
    _merchant_id, user_id = _merchant_and_member(fake_client)
    link = _create_payment_link(user_id)
    _patch_checkout_client(monkeypatch)

    _pay(link["public_slug"])

    order = fake_client.table("checkout_orders")._table.rows[0]
    assert order["order_id"]
    assert order["payment_token"] == "63850827"
    assert order["qr"] == "QRDATA"
    assert order["payment_gateway_url"]  # decoded, non-empty
    assert order["raw_response"] == CREATE_ORDER_SUCCESS_RESPONSE

    collection = fake_client.table("collections")._table.rows[0]
    assert collection["provider_transid"]
    assert collection["provider_reference"] == WALLET_PAYMENT_PENDING_RESPONSE["reference"]
    assert collection["provider_result"] == "PENDING"
    assert collection["provider_resultcode"] == "111"
    assert collection["raw_response"] == WALLET_PAYMENT_PENDING_RESPONSE


def test_create_order_minimal_is_called_before_wallet_payment(fake_client, monkeypatch):
    _merchant_id, user_id = _merchant_and_member(fake_client)
    link = _create_payment_link(user_id)
    fake = _patch_checkout_client(monkeypatch)

    _pay(link["public_slug"])

    call_names = [name for name, _ in fake.calls]
    assert call_names == ["create_order_minimal", "process_wallet_payment"]

    # wallet-payment's order_id must be the exact one create-order-minimal
    # generated — not a coincidence, an explicit hand-off.
    order_call = fake.calls[0][1]
    payment_call = fake.calls[1][1]
    assert payment_call["order_id"] == order_call["order_id"]


def test_customer_phone_is_normalized_before_reaching_selcom(fake_client, monkeypatch):
    _merchant_id, user_id = _merchant_and_member(fake_client)
    link = _create_payment_link(user_id)
    fake = _patch_checkout_client(monkeypatch)

    response = _pay(link["public_slug"], phone="+255 747 730 270")

    assert response.status_code == 202, response.text
    order_call = fake.calls[0][1]
    payment_call = fake.calls[1][1]
    assert order_call["buyer_phone"] == "255747730270"
    assert payment_call["msisdn"] == "255747730270"


# --- payment link status guards -------------------------------------------------------


def test_expired_payment_link_rejected(fake_client, monkeypatch):
    _merchant_id, user_id = _merchant_and_member(fake_client)
    link = _create_payment_link(user_id)
    fake = _patch_checkout_client(monkeypatch)
    fake_client.table("payment_links")._table.rows[0]["expires_at"] = "2020-01-01T00:00:00+00:00"
    fake_client.table("payment_links")._table.rows[0]["status"] = "ACTIVE"

    response = _pay(link["public_slug"])

    assert response.status_code == 409, response.text
    assert len(fake.calls) == 0
    assert len(fake_client.table("collections")._table.rows) == 0


def test_cancelled_payment_link_rejected(fake_client, monkeypatch):
    _merchant_id, user_id = _merchant_and_member(fake_client)
    link = _create_payment_link(user_id)
    fake = _patch_checkout_client(monkeypatch)
    fake_client.table("payment_links")._table.rows[0]["status"] = "CANCELLED"

    response = _pay(link["public_slug"])

    assert response.status_code == 409, response.text
    assert len(fake.calls) == 0


def test_paid_payment_link_rejected(fake_client, monkeypatch):
    _merchant_id, user_id = _merchant_and_member(fake_client)
    link = _create_payment_link(user_id)
    fake = _patch_checkout_client(monkeypatch)
    fake_client.table("payment_links")._table.rows[0]["status"] = "PAID"

    response = _pay(link["public_slug"])

    assert response.status_code == 409, response.text
    assert len(fake.calls) == 0


def test_unknown_payment_link_returns_404(fake_client, monkeypatch):
    _patch_checkout_client(monkeypatch)
    response = _pay("does-not-exist")
    assert response.status_code == 404


# --- no crediting -----------------------------------------------------------------


def test_pending_result_does_not_credit_merchant_or_mark_link_paid(fake_client, monkeypatch):
    merchant_id, user_id = _merchant_and_member(fake_client)
    fake_client.seed(
        "ledger_accounts",
        {
            "merchant_id": str(merchant_id),
            "name": "Merchant Wallet (test)",
            "account_type": "liability",
            "purpose": "merchant_wallet",
            "currency": "TZS",
            "balance": "0",
        },
    )
    link = _create_payment_link(user_id)
    _patch_checkout_client(monkeypatch)

    _pay(link["public_slug"])

    balance = fake_client.table("ledger_accounts")._table.rows[0]["balance"]
    assert Decimal(str(balance)) == Decimal(0)
    assert fake_client.table("payment_links")._table.rows[0]["status"] == "ACTIVE"
    assert fake_client.table("payment_links")._table.rows[0].get("paid_at") is None
    assert len(fake_client.table("ledger_entries")._table.rows) == 0


def test_immediate_success_result_still_does_not_credit(fake_client, monkeypatch):
    """Even the rare case where Selcom's wallet-payment call itself
    returns resultcode 000 synchronously must not be treated as a
    completed, crediting-worthy payment in this task's implementation —
    see app/services/wallet_push.py's module docstring."""
    _merchant_id, user_id = _merchant_and_member(fake_client)
    link = _create_payment_link(user_id)
    _patch_checkout_client(
        monkeypatch,
        payment_response={
            "reference": "REF-1",
            "resultcode": "000",
            "result": "SUCCESS",
            "message": "OK",
            "data": [],
        },
    )

    response = _pay(link["public_slug"])

    assert response.status_code == 202, response.text
    assert response.json()["data"]["payment_status"] == "pending"
    assert fake_client.table("collections")._table.rows[0]["status"] == "processing"
    assert fake_client.table("payment_links")._table.rows[0]["status"] == "ACTIVE"


# --- duplicate attempts -------------------------------------------------------------


def test_duplicate_attempt_with_same_idempotency_key_does_not_push_twice(fake_client, monkeypatch):
    _merchant_id, user_id = _merchant_and_member(fake_client)
    link = _create_payment_link(user_id)
    fake = _patch_checkout_client(monkeypatch)
    key = _idem()

    first = _pay(link["public_slug"], idempotency_key=key)
    second = _pay(link["public_slug"], idempotency_key=key)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["data"]["collection_id"] == second.json()["data"]["collection_id"]
    assert len(fake.calls) == 2  # one create_order_minimal + one process_wallet_payment, not four


def test_duplicate_attempt_with_different_idempotency_key_does_not_push_twice(fake_client, monkeypatch):
    """The real "no double-credit" guard: a customer who retries with a
    fresh Idempotency-Key (e.g. a page refresh generating a new UUID)
    must still not trigger a second real push while one is already
    in flight."""
    _merchant_id, user_id = _merchant_and_member(fake_client)
    link = _create_payment_link(user_id)
    fake = _patch_checkout_client(monkeypatch)

    first = _pay(link["public_slug"], idempotency_key=_idem())
    second = _pay(link["public_slug"], idempotency_key=_idem())

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["data"]["collection_id"] == second.json()["data"]["collection_id"]
    assert len(fake.calls) == 2
    assert len(fake_client.table("collections")._table.rows) == 1


def test_second_attempt_after_first_order_creation_reuses_the_order(fake_client, monkeypatch):
    """"Create Selcom minimal order if one does not already exist for
    this attempt" — a checkout_order left in status="created" (e.g. a
    prior attempt that never reached wallet-payment) must be reused,
    not recreated, on a fresh attempt."""
    _merchant_id, user_id = _merchant_and_member(fake_client)
    link = _create_payment_link(user_id)
    fake = _patch_checkout_client(monkeypatch)

    from app.services.checkout_orders import (
        get_or_create_checkout_order_for_payment_link,
    )

    async def _seed_order():
        return await get_or_create_checkout_order_for_payment_link(
            fake_client, payment_link=link, buyer_phone="255747730270"
        )

    import asyncio

    order = asyncio.run(_seed_order())
    assert len(fake.calls) == 1

    response = _pay(link["public_slug"])

    assert response.status_code == 202, response.text
    assert len(fake_client.table("checkout_orders")._table.rows) == 1
    # Only process_wallet_payment was called this time — the order was reused.
    assert len(fake.calls) == 2
    assert fake.calls[1][1]["order_id"] == order["order_id"]


# --- failure handling ----------------------------------------------------------------


def test_wallet_payment_clean_failure_marks_collection_failed(fake_client, monkeypatch):
    _merchant_id, user_id = _merchant_and_member(fake_client)
    link = _create_payment_link(user_id)
    _patch_checkout_client(monkeypatch, payment_response=WALLET_PAYMENT_FAILED_RESPONSE)

    response = _pay(link["public_slug"])

    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["payment_status"] == "failed"
    assert fake_client.table("collections")._table.rows[0]["status"] == "failed"
    assert fake_client.table("collections")._table.rows[0]["provider_resultcode"] == "651"


def test_order_creation_failure_never_attempts_wallet_payment(fake_client, monkeypatch):
    """"Do not continue if create-order-minimal is not working" — applied
    per-request, not just at the go/no-go gate before this task started."""
    _merchant_id, user_id = _merchant_and_member(fake_client)
    link = _create_payment_link(user_id)
    fake = _patch_checkout_client(monkeypatch, order_response=CREATE_ORDER_FAILED_RESPONSE)

    response = _pay(link["public_slug"])

    assert response.status_code == 202, response.text
    assert response.json()["data"]["payment_status"] == "failed"
    call_names = [name for name, _ in fake.calls]
    assert call_names == ["create_order_minimal"]  # wallet-payment never reached
    assert fake_client.table("collections")._table.rows[0]["status"] == "failed"


def test_malformed_selcom_response_does_not_crash(fake_client, monkeypatch):
    """An empty/garbage response from Selcom must be handled safely —
    parse_wallet_payment_response() treats missing fields as failed, not
    an unhandled exception."""
    _merchant_id, user_id = _merchant_and_member(fake_client)
    link = _create_payment_link(user_id)
    _patch_checkout_client(monkeypatch, payment_response={})

    response = _pay(link["public_slug"])

    assert response.status_code == 202, response.text
    assert response.json()["data"]["payment_status"] == "failed"
