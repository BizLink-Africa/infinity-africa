import uuid
from decimal import Decimal

import pytest

from app.core.errors import InsufficientBalanceError
from app.services.ledger import (
    get_wallet_balance,
    post_collection_entries,
    post_disbursement_entries,
    reverse_disbursement_entries,
)
from tests.fakes import FakeSupabaseClient


def _entries_for(client: FakeSupabaseClient, transaction_id: uuid.UUID) -> list[dict]:
    return [
        row
        for row in client.table("ledger_entries")._table.rows
        if row["transaction_id"] == str(transaction_id)
    ]


def test_post_collection_entries_is_balanced():
    client = FakeSupabaseClient()
    transaction_id = uuid.uuid4()
    merchant_id = uuid.uuid4()

    post_collection_entries(
        client,
        transaction_id=transaction_id,
        merchant_id=merchant_id,
        gross_amount=Decimal("1000.00"),
        fee_amount=Decimal("15.00"),
        net_amount=Decimal("985.00"),
        currency="TZS",
    )

    entries = _entries_for(client, transaction_id)
    debits = sum(Decimal(e["amount"]) for e in entries if e["direction"] == "debit")
    credits = sum(Decimal(e["amount"]) for e in entries if e["direction"] == "credit")

    assert debits == credits == Decimal("1000.00")
    assert len(entries) == 3  # settlement debit, wallet credit, platform revenue credit


def test_post_collection_entries_skips_zero_fee_leg():
    client = FakeSupabaseClient()
    transaction_id = uuid.uuid4()
    merchant_id = uuid.uuid4()

    post_collection_entries(
        client,
        transaction_id=transaction_id,
        merchant_id=merchant_id,
        gross_amount=Decimal("500.00"),
        fee_amount=Decimal(0),
        net_amount=Decimal("500.00"),
        currency="TZS",
    )

    entries = _entries_for(client, transaction_id)
    assert len(entries) == 2  # no platform-revenue leg when there's no fee

    debits = sum(Decimal(e["amount"]) for e in entries if e["direction"] == "debit")
    credits = sum(Decimal(e["amount"]) for e in entries if e["direction"] == "credit")
    assert debits == credits == Decimal("500.00")


def test_post_disbursement_entries_is_balanced():
    client = FakeSupabaseClient()
    transaction_id = uuid.uuid4()
    merchant_id = uuid.uuid4()

    # Fund the wallet first — post_disbursement_entries now enforces that a
    # merchant_wallet balance can never go negative (see
    # test_post_disbursement_entries_rejects_insufficient_balance below).
    post_collection_entries(
        client,
        transaction_id=uuid.uuid4(),
        merchant_id=merchant_id,
        gross_amount=Decimal("1000.00"),
        fee_amount=Decimal(0),
        net_amount=Decimal("1000.00"),
        currency="TZS",
    )

    post_disbursement_entries(
        client,
        transaction_id=transaction_id,
        merchant_id=merchant_id,
        amount=Decimal("250.00"),
        currency="TZS",
    )

    entries = _entries_for(client, transaction_id)
    debits = sum(Decimal(e["amount"]) for e in entries if e["direction"] == "debit")
    credits = sum(Decimal(e["amount"]) for e in entries if e["direction"] == "credit")

    assert debits == credits == Decimal("250.00")
    assert len(entries) == 2
    assert get_wallet_balance(client, merchant_id=merchant_id, currency="TZS") == Decimal("750.00")


def test_post_disbursement_entries_rejects_insufficient_balance():
    client = FakeSupabaseClient()
    merchant_id = uuid.uuid4()
    disbursement_transaction_id = uuid.uuid4()

    post_collection_entries(
        client,
        transaction_id=uuid.uuid4(),
        merchant_id=merchant_id,
        gross_amount=Decimal("100.00"),
        fee_amount=Decimal(0),
        net_amount=Decimal("100.00"),
        currency="TZS",
    )

    with pytest.raises(InsufficientBalanceError):
        post_disbursement_entries(
            client,
            transaction_id=disbursement_transaction_id,
            merchant_id=merchant_id,
            amount=Decimal("250.00"),
            currency="TZS",
        )

    # Rejected as a whole batch — no entries posted for the disbursement's
    # own transaction_id (the funding collection's 2 entries are untouched).
    assert _entries_for(client, disbursement_transaction_id) == []
    assert get_wallet_balance(client, merchant_id=merchant_id, currency="TZS") == Decimal("100.00")


def test_reverse_disbursement_entries_restores_balance():
    client = FakeSupabaseClient()
    merchant_id = uuid.uuid4()
    transaction_id = uuid.uuid4()

    post_collection_entries(
        client,
        transaction_id=uuid.uuid4(),
        merchant_id=merchant_id,
        gross_amount=Decimal("500.00"),
        fee_amount=Decimal(0),
        net_amount=Decimal("500.00"),
        currency="TZS",
    )
    post_disbursement_entries(
        client, transaction_id=transaction_id, merchant_id=merchant_id, amount=Decimal("300.00"), currency="TZS"
    )
    assert get_wallet_balance(client, merchant_id=merchant_id, currency="TZS") == Decimal("200.00")

    reverse_disbursement_entries(
        client, transaction_id=transaction_id, merchant_id=merchant_id, amount=Decimal("300.00"), currency="TZS"
    )

    assert get_wallet_balance(client, merchant_id=merchant_id, currency="TZS") == Decimal("500.00")
    entries = _entries_for(client, transaction_id)
    assert len(entries) == 4  # reservation (debit+credit) + reversal (credit+debit)
    debits = sum(Decimal(e["amount"]) for e in entries if e["direction"] == "debit")
    credits = sum(Decimal(e["amount"]) for e in entries if e["direction"] == "credit")
    assert debits == credits == Decimal("600.00")  # nets to zero movement overall


def test_ledger_accounts_are_reused_not_duplicated():
    client = FakeSupabaseClient()
    merchant_id = uuid.uuid4()

    post_collection_entries(
        client,
        transaction_id=uuid.uuid4(),
        merchant_id=merchant_id,
        gross_amount=Decimal("100.00"),
        fee_amount=Decimal("1.00"),
        net_amount=Decimal("99.00"),
        currency="TZS",
    )
    post_collection_entries(
        client,
        transaction_id=uuid.uuid4(),
        merchant_id=merchant_id,
        gross_amount=Decimal("100.00"),
        fee_amount=Decimal("1.00"),
        net_amount=Decimal("99.00"),
        currency="TZS",
    )

    accounts = client.table("ledger_accounts")._table.rows
    wallet_accounts = [a for a in accounts if a["purpose"] == "merchant_wallet"]
    settlement_accounts = [a for a in accounts if a["purpose"] == "settlement_clearing"]
    revenue_accounts = [a for a in accounts if a["purpose"] == "platform_revenue"]

    assert len(wallet_accounts) == 1
    assert len(settlement_accounts) == 1
    assert len(revenue_accounts) == 1
