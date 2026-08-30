"""Confirms collection fee computation is genuinely untouched by the MVP
pricing change (fix: apply pricing fees to collections only —
withdrawal fees removed, see app/services/withdrawals/fee_calculator.py).

Every collection flow (Request Collection, Wallet Push, Push to Selcom
Pesa, TanQR, Payment Links, Pay by Link, Invoices, API collections)
funnels through the single shared chokepoint
app/services/collections.py::create_processing_transaction, which was
never modified by this change — it still computes
fee_amount = gross * settings.platform_fee_percentage / 100 and
net_amount = gross - fee_amount, exactly as before. Each individual
flow's own test file (test_collections.py, test_wallet_push_collection.py,
test_payment_links.py, test_invoices.py, test_collections_api.py,
test_pay_by_link.py, ...) already exercises its own endpoint end-to-end
and continues to pass unmodified — this file adds the one thing that
was genuinely worth a fresh, explicit test: that collection fees are
computed completely independently of merchant_pricing_rules (the table
withdrawal fees used to read from, and that this MVP change stopped
reading from for withdrawals too) — collections were never wired to
that table, and must stay that way.
"""

import uuid
from decimal import Decimal

from app.config import get_settings
from app.services.collections import create_processing_transaction
from tests.factories import create_merchant, create_pricing_rule


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
