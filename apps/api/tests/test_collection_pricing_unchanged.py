"""Confirms collection fee computation across two MVP pricing changes:

1. "fix: apply pricing fees to collections only" (2026-08-31) — withdrawal
   fees removed, see app/services/withdrawals/fee_calculator.py.
2. "Super Admin pricing rule requirement" (2026-08-31, same day) —
   collection fees became per-merchant/per-channel configurable via
   app/services/collection_pricing.py + merchant_collection_pricing_rules,
   replacing the flat-only settings.platform_fee_percentage model this
   file originally tested against exclusively.

Every collection flow (Request Collection, Wallet Push, Push to Selcom
Pesa, TanQR, Payment Links, Pay by Link, Invoices, API collections)
still funnels through the single shared chokepoint
app/services/collections.py::create_processing_transaction — unchanged
by either update — which now calls
app/services/collection_pricing.py::calculate_collection_fee instead of
computing the flat rate inline; that function's own math/precedence
tests live in test_collection_pricing.py. Each individual flow's own
test file (test_collections.py, test_wallet_push_collection.py,
test_payment_links.py, test_invoices.py, test_collections_api.py,
test_pay_by_link.py, ...) already exercises its own endpoint end-to-end
and continues to pass unmodified. What's worth a fresh, explicit test
here specifically: fee computation is still completely independent of
merchant_pricing_rules (the WITHDRAWAL-only table — collections were
never wired to it and must stay that way, even now that they have their
own, separate per-merchant pricing table), and a real per-merchant
collection pricing rule genuinely reaches a real collection-creation
endpoint end to end, not just the calculator function in isolation.
"""

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services.collections import create_processing_transaction
from tests.factories import (
    TEST_JWT_SECRET,
    auth_headers,
    create_collection_pricing_rule,
    create_merchant,
    create_pricing_rule,
    make_merchant_member,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("MOCK_PROVIDER_FAILURE_RATE", "0")
    monkeypatch.setenv("MOCK_PROVIDER_LATENCY_SECONDS", "0")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _merchant_id(fake_client) -> uuid.UUID:
    return uuid.UUID(create_merchant(fake_client)["id"])


def test_collection_fee_uses_the_platform_fee_percentage_setting(fake_client, monkeypatch):
    monkeypatch.setenv("PLATFORM_FEE_PERCENTAGE", "1.5")
    get_settings.cache_clear()
    merchant_id = _merchant_id(fake_client)

    transaction = create_processing_transaction(
        fake_client,
        merchant_id=merchant_id,
        method="STK_PUSH",
        collection_id=str(uuid.uuid4()),
        provider_reference="REF-1",
        amount=Decimal("100000.00"),
        currency="TZS",
    )

    assert Decimal(transaction["gross_amount"]) == Decimal("100000.00")
    assert Decimal(transaction["fee_amount"]) == Decimal("1500.00")
    assert Decimal(transaction["net_amount"]) == Decimal("98500.00")
    assert Decimal(transaction["net_amount"]) == Decimal(transaction["gross_amount"]) - Decimal(
        transaction["fee_amount"]
    )
    get_settings.cache_clear()


def test_collection_fee_applies_identically_regardless_of_method_label(fake_client):
    """One shared chokepoint, one fee calculation — Wallet Push
    (STK_PUSH/USSD_PUSH), Push to Selcom Pesa (SELCOM_PESA_PUSH), TanQR
    (DYNAMIC_QR), and the hosted-checkout flow every Payment Link/Pay by
    Link/Invoice "Pay Now" link uses (HOSTED_CHECKOUT) all compute the
    exact same fee for the exact same amount."""
    merchant_id = _merchant_id(fake_client)

    methods = ["STK_PUSH", "SELCOM_PESA_PUSH", "DYNAMIC_QR", "HOSTED_CHECKOUT"]
    fees = set()
    for method in methods:
        transaction = create_processing_transaction(
            fake_client,
            merchant_id=merchant_id,
            method=method,
            collection_id=str(uuid.uuid4()),
            provider_reference=f"REF-{method}",
            amount=Decimal("50000.00"),
            currency="TZS",
        )
        assert Decimal(transaction["net_amount"]) == Decimal(transaction["gross_amount"]) - Decimal(
            transaction["fee_amount"]
        )
        assert Decimal(transaction["fee_amount"]) > 0
        fees.add(transaction["fee_amount"])

    assert len(fees) == 1


def test_collection_fee_is_never_affected_by_merchant_pricing_rules(fake_client):
    """merchant_pricing_rules is the table withdrawal fees used to read
    from (and, as of this MVP change, no longer do — see
    app/services/withdrawals/fee_calculator.py). Collections were never
    wired to it at all: a merchant/platform rule configured there
    (however extreme) must have zero effect on a collection's fee."""
    merchant_id = _merchant_id(fake_client)
    create_pricing_rule(
        fake_client,
        merchant_id=merchant_id,
        percentage_fee="50",
        flat_fee="99999",
        processor_fee_flat="500",
        processor_fee_pass_through=True,
    )

    with_rule = create_processing_transaction(
        fake_client,
        merchant_id=merchant_id,
        method="STK_PUSH",
        collection_id=str(uuid.uuid4()),
        provider_reference="REF-with-rule",
        amount=Decimal("100000.00"),
        currency="TZS",
    )

    other_merchant_id = _merchant_id(fake_client)
    without_rule = create_processing_transaction(
        fake_client,
        merchant_id=other_merchant_id,
        method="STK_PUSH",
        collection_id=str(uuid.uuid4()),
        provider_reference="REF-without-rule",
        amount=Decimal("100000.00"),
        currency="TZS",
    )

    assert with_rule["fee_amount"] == without_rule["fee_amount"]
    assert with_rule["net_amount"] == without_rule["net_amount"]


def test_a_real_merchant_collection_pricing_rule_reaches_a_real_endpoint_end_to_end(fake_client):
    """Closes the loop between the pricing engine's own unit tests
    (test_collection_pricing.py) and the real customer-facing collection
    endpoint — POST /v1/collections/stk-push all the way through to the
    resulting transactions row, with a genuine per-merchant negotiated
    rate applied, not the flat platform default."""
    merchant = create_merchant(fake_client)
    merchant_id = uuid.UUID(merchant["id"])
    admin_id = uuid.uuid4()
    make_merchant_member(fake_client, merchant_id, admin_id, "MERCHANT_ADMIN")
    create_collection_pricing_rule(fake_client, merchant_id=merchant_id, percentage_fee="0.4", label="Merchant A rate")

    response = client.post(
        "/v1/collections/stk-push",
        headers={**auth_headers(admin_id), "Idempotency-Key": str(uuid.uuid4())},
        json={"merchant_id": str(merchant_id), "amount": "10000.00", "customer_phone": "+255700000000"},
    )

    assert response.status_code == 202, response.text
    transaction = next(
        t for t in fake_client.table("transactions")._table.rows if t["merchant_id"] == str(merchant_id)
    )
    assert Decimal(transaction["fee_amount"]) == Decimal("40.00")
    assert Decimal(transaction["net_amount"]) == Decimal("9960.00")
