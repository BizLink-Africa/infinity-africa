"""app/services/checkout_reconciliation.py — the shared completion path
both the webhook and the manual refresh endpoints use. Sets up a real
"processing" wallet-push collection (via the actual
execute_wallet_push_for_payment_link() flow, same as test_wallet_push.py)
so these tests exercise the true fixture shape (linked transaction,
checkout_order, payment_link) rather than a hand-rolled approximation.

Credit rule under test: a collection is only ever credited when
result == "SUCCESS" and resultcode == "000" and payment_status ==
"COMPLETED" all agree — see checkout_reconciliation.py's module
docstring.
"""

import asyncio
import uuid
from decimal import Decimal

import pytest

from app.services.checkout_reconciliation import (
    complete_checkout_collection_once,
    map_checkout_status_to_provider_status,
    refresh_checkout_collection_status,
)
from app.services.wallet_push import execute_wallet_push_for_payment_link
from tests.factories import create_merchant, make_merchant_member

WALLET_PAYMENT_PENDING_RESPONSE = {
    "reference": "0289999288",
    "resultcode": "111",
    "result": "PENDING",
    "message": "Request in progress.",
    "data": [],
}

CREATE_ORDER_SUCCESS_RESPONSE = {
    "reference": "S20690427372",
    "resultcode": "000",
    "result": "SUCCESS",
    "message": "Payment notification logged",
    "data": [{"payment_token": "TOKEN", "payment_gateway_url": "aHR0cHM6Ly9leGFtcGxlLmNvbS9wYXk=", "qr": "QR"}],
}


class _FakeSelcomCheckoutClient:
    def __init__(self, *, credentials=None, order_response=None, payment_response=None):
        self._order_response = order_response or CREATE_ORDER_SUCCESS_RESPONSE
        self._payment_response = payment_response or WALLET_PAYMENT_PENDING_RESPONSE

    async def create_order_minimal(self, **kwargs):
        from app.services.selcom_checkout.parsing import (
            parse_create_order_minimal_response,
        )

        return parse_create_order_minimal_response(self._order_response)

    async def process_wallet_payment(self, **kwargs):
        from app.services.selcom_checkout.parsing import parse_wallet_payment_response

        return parse_wallet_payment_response(self._payment_response)


def _patch_checkout_client(monkeypatch):
    import app.services.checkout_orders as checkout_orders_module
    import app.services.wallet_push as wallet_push_module

    fake = _FakeSelcomCheckoutClient()
    monkeypatch.setattr(checkout_orders_module, "SelcomCheckoutHTTPClient", lambda **kwargs: fake)
    monkeypatch.setattr(wallet_push_module, "SelcomCheckoutHTTPClient", lambda **kwargs: fake)


def _seed_pending_collection(fake_client, monkeypatch, *, with_invoice: bool = False) -> tuple[dict, dict]:
    """Real setup, not a shortcut: creates a merchant, a payment link (and
    optionally a linked invoice), then runs the actual wallet-push flow
    to get a genuine "processing" collection with its transaction/
    checkout_order links intact."""
    _patch_checkout_client(monkeypatch)
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    user_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, user_id, "MERCHANT_ADMIN")
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

    payment_link = fake_client.seed(
        "payment_links",
        {
            "merchant_id": str(merchant_id),
            "amount": "1000.00",
            "currency": "TZS",
            "status": "ACTIVE",
            "allowed_payment_methods": ["STK_PUSH"],
            "public_slug": "test-slug-" + uuid.uuid4().hex[:8],
        },
    )

    if with_invoice:
        invoice = fake_client.seed(
            "invoices",
            {
                "merchant_id": str(merchant_id),
                "payment_link_id": payment_link["id"],
                "invoice_number": "INV-TEST-1",
                "total_amount": "1000.00",
                "amount_paid": "0",
                "status": "SENT",
            },
        )
    else:
        invoice = None

    collection = asyncio.run(
        execute_wallet_push_for_payment_link(fake_client, payment_link=payment_link, buyer_phone="255747730270")
    )
    assert collection["status"] == "processing"
    return collection, {"merchant_id": merchant_id, "payment_link": payment_link, "invoice": invoice}


# --- pure mapping function ----------------------------------------------------------


@pytest.mark.parametrize(
    ("payment_status", "result", "resultcode", "expected"),
    [
        ("COMPLETED", "SUCCESS", "000", "successful"),
        ("COMPLETED", "FAIL", "651", "processing"),  # inconsistent — never silently credited or failed
        ("PENDING", None, "111", "processing"),
        ("INPROGRESS", None, "927", "processing"),
        ("CANCELLED", None, None, "failed"),
        ("USERCANCELLED", None, None, "failed"),
        ("REJECTED", None, None, "failed"),
        (None, "SUCCESS", "000", "successful"),  # bare wallet-payment result, no payment_status yet
        (None, None, "111", "processing"),
        (None, None, "999", "processing"),
        (None, None, "651", "failed"),
    ],
)
def test_map_checkout_status_to_provider_status(payment_status, result, resultcode, expected):
    assert (
        map_checkout_status_to_provider_status(payment_status=payment_status, result=result, resultcode=resultcode)
        == expected
    )


# --- complete_checkout_collection_once: crediting ------------------------------------


def test_completed_status_credits_merchant_exactly_once(fake_client, monkeypatch):
    collection, _ctx = _seed_pending_collection(fake_client, monkeypatch)

    resolved = asyncio.run(
        complete_checkout_collection_once(
            fake_client,
            collection_id=uuid.UUID(collection["id"]),
            payment_status="COMPLETED",
            result="SUCCESS",
            resultcode="000",
            reference="S20690471578",
            transid=collection["provider_transid"],
            channel="TIGOPESA",
            raw_response={"payment_status": "COMPLETED"},
        )
    )

    assert resolved["status"] == "successful"
    balance = fake_client.table("ledger_accounts")._table.rows[0]["balance"]
    assert Decimal(str(balance)) == Decimal("985.00")

    link = fake_client.table("payment_links")._table.rows[0]
    assert link["status"] == "PAID"
    assert link["paid_at"] is not None

    order = fake_client.table("checkout_orders")._table.rows[0]
    assert order["status"] == "completed"

    notifications = fake_client.table("notifications")._table.rows
    assert any(n["notification_type"] == "payment_received" for n in notifications)


def test_duplicate_completion_does_not_double_credit(fake_client, monkeypatch):
    collection, _ctx = _seed_pending_collection(fake_client, monkeypatch)
    collection_id = uuid.UUID(collection["id"])

    kwargs = {
        "payment_status": "COMPLETED",
        "result": "SUCCESS",
        "resultcode": "000",
        "reference": "S20690471578",
        "transid": collection["provider_transid"],
        "channel": "TIGOPESA",
        "raw_response": {"payment_status": "COMPLETED"},
    }
    asyncio.run(complete_checkout_collection_once(fake_client, collection_id=collection_id, **kwargs))
    asyncio.run(complete_checkout_collection_once(fake_client, collection_id=collection_id, **kwargs))
    asyncio.run(complete_checkout_collection_once(fake_client, collection_id=collection_id, **kwargs))

    balance = fake_client.table("ledger_accounts")._table.rows[0]["balance"]
    assert Decimal(str(balance)) == Decimal("985.00")  # not 2000, not 3000
    notifications = [
        n for n in fake_client.table("notifications")._table.rows if n["notification_type"] == "payment_received"
    ]
    assert len(notifications) == 1  # not re-notified on the repeat calls


def test_invoice_becomes_paid_when_linked(fake_client, monkeypatch):
    collection, _ctx = _seed_pending_collection(fake_client, monkeypatch, with_invoice=True)

    asyncio.run(
        complete_checkout_collection_once(
            fake_client,
            collection_id=uuid.UUID(collection["id"]),
            payment_status="COMPLETED",
            result="SUCCESS",
            resultcode="000",
            reference="S20690471578",
            transid=collection["provider_transid"],
            channel="TIGOPESA",
            raw_response={},
        )
    )

    invoice = fake_client.table("invoices")._table.rows[0]
    assert invoice["status"] == "PAID"
    assert Decimal(str(invoice["amount_paid"])) == Decimal("1000.00")


# --- complete_checkout_collection_once: no crediting on non-completion ---------------


@pytest.mark.parametrize("payment_status", ["PENDING", "INPROGRESS"])
def test_still_pending_payment_status_does_not_credit(fake_client, monkeypatch, payment_status):
    collection, _ctx = _seed_pending_collection(fake_client, monkeypatch)

    resolved = asyncio.run(
        complete_checkout_collection_once(
            fake_client,
            collection_id=uuid.UUID(collection["id"]),
            payment_status=payment_status,
            result="PENDING",
            resultcode="111",
            reference="0289999288",
            transid=collection["provider_transid"],
            channel="TIGOPESA",
            raw_response={},
        )
    )

    assert resolved["status"] == "processing"
    balance = fake_client.table("ledger_accounts")._table.rows[0]["balance"]
    assert Decimal(str(balance)) == Decimal(0)
    assert fake_client.table("payment_links")._table.rows[0]["status"] == "ACTIVE"


@pytest.mark.parametrize("payment_status", ["CANCELLED", "USERCANCELLED", "REJECTED"])
def test_terminal_non_completed_payment_status_marks_failed_without_crediting(fake_client, monkeypatch, payment_status):
    collection, _ctx = _seed_pending_collection(fake_client, monkeypatch)

    resolved = asyncio.run(
        complete_checkout_collection_once(
            fake_client,
            collection_id=uuid.UUID(collection["id"]),
            payment_status=payment_status,
            result="FAIL",
            resultcode="651",
            reference="0289999288",
            transid=collection["provider_transid"],
            channel="TIGOPESA",
            raw_response={},
        )
    )

    assert resolved["status"] == "failed"
    balance = fake_client.table("ledger_accounts")._table.rows[0]["balance"]
    assert Decimal(str(balance)) == Decimal(0)
    assert fake_client.table("payment_links")._table.rows[0]["status"] == "ACTIVE"


def test_raw_response_stored_safely(fake_client, monkeypatch):
    collection, _ctx = _seed_pending_collection(fake_client, monkeypatch)
    raw = {"payment_status": "COMPLETED", "some_field": "some_value"}

    asyncio.run(
        complete_checkout_collection_once(
            fake_client,
            collection_id=uuid.UUID(collection["id"]),
            payment_status="COMPLETED",
            result="SUCCESS",
            resultcode="000",
            reference="S20690471578",
            transid=collection["provider_transid"],
            channel="TIGOPESA",
            raw_response=raw,
        )
    )

    stored = fake_client.table("collections")._table.rows[0]
    assert stored["raw_response"] == raw
    assert stored["provider_payment_status"] == "COMPLETED"
    assert stored["channel"] == "TIGOPESA"


# --- refresh_checkout_collection_status ----------------------------------------------


def test_refresh_status_completed_credits_merchant_once(fake_client, monkeypatch):
    collection, _ctx = _seed_pending_collection(fake_client, monkeypatch)

    import app.services.checkout_reconciliation as reconciliation_module

    class _FakeStatusClient:
        def __init__(self, *, credentials=None):
            pass

        async def get_order_status(self, *, order_id):
            from app.services.selcom_checkout.parsing import parse_order_status_response

            return parse_order_status_response(
                {
                    "reference": "S20690471578",
                    "resultcode": "000",
                    "result": "SUCCESS",
                    "message": "OK",
                    "data": [{"order_id": order_id, "payment_status": "COMPLETED", "transid": collection["provider_transid"]}],
                }
            )

    monkeypatch.setattr(reconciliation_module, "SelcomCheckoutHTTPClient", lambda **kwargs: _FakeStatusClient())

    resolved = asyncio.run(refresh_checkout_collection_status(fake_client, collection_id=uuid.UUID(collection["id"])))
    assert resolved["status"] == "successful"

    balance = fake_client.table("ledger_accounts")._table.rows[0]["balance"]
    assert Decimal(str(balance)) == Decimal("985.00")

    # A second refresh must not double-credit.
    resolved_again = asyncio.run(
        refresh_checkout_collection_status(fake_client, collection_id=uuid.UUID(collection["id"]))
    )
    assert resolved_again["status"] == "successful"
    balance = fake_client.table("ledger_accounts")._table.rows[0]["balance"]
    assert Decimal(str(balance)) == Decimal("985.00")
