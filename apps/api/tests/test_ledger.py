import uuid
from decimal import Decimal

import pytest

from app.core.errors import InsufficientBalanceError
from app.core.pagination import PaginationParams
from app.services.ledger import (
    get_wallet_balance,
    list_wallet_ledger,
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


def test_post_disbursement_entries_with_fee_adds_revenue_leg():
    client = FakeSupabaseClient()
    merchant_id = uuid.uuid4()
    transaction_id = uuid.uuid4()

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
        amount=Decimal("500.00"),
        fee_amount=Decimal("20.00"),
        currency="TZS",
    )

    entries = _entries_for(client, transaction_id)
    assert len(entries) == 3  # wallet debit, settlement credit, platform revenue credit
    debits = sum(Decimal(e["amount"]) for e in entries if e["direction"] == "debit")
    credits = sum(Decimal(e["amount"]) for e in entries if e["direction"] == "credit")
    assert debits == credits == Decimal("520.00")
    # Wallet debited for amount + fee, not just amount.
    assert get_wallet_balance(client, merchant_id=merchant_id, currency="TZS") == Decimal("480.00")


def test_reverse_disbursement_entries_with_fee_restores_full_balance():
    client = FakeSupabaseClient()
    merchant_id = uuid.uuid4()
    transaction_id = uuid.uuid4()

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
        amount=Decimal("500.00"),
        fee_amount=Decimal("20.00"),
        currency="TZS",
    )
    assert get_wallet_balance(client, merchant_id=merchant_id, currency="TZS") == Decimal("480.00")

    reverse_disbursement_entries(
        client,
        transaction_id=transaction_id,
        merchant_id=merchant_id,
        amount=Decimal("500.00"),
        fee_amount=Decimal("20.00"),
        currency="TZS",
    )

    assert get_wallet_balance(client, merchant_id=merchant_id, currency="TZS") == Decimal("1000.00")
    entries = _entries_for(client, transaction_id)
    assert len(entries) == 6  # 3-leg reservation + 3-leg reversal
    debits = sum(Decimal(e["amount"]) for e in entries if e["direction"] == "debit")
    credits = sum(Decimal(e["amount"]) for e in entries if e["direction"] == "credit")
    assert debits == credits


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


def test_list_wallet_ledger_computes_running_balance_newest_first():
    """ledger_entries has no stored per-row balance — list_wallet_ledger
    computes balance_after itself from ledger_accounts.balance's sign
    convention (credit +, debit -), newest entry first (see
    app/services/ledger.py::list_wallet_ledger)."""
    client = FakeSupabaseClient()
    merchant_id = uuid.uuid4()

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
        transaction_id=uuid.uuid4(),
        merchant_id=merchant_id,
        amount=Decimal("300.00"),
        currency="TZS",
    )

    rows, total = list_wallet_ledger(
        client, merchant_id=merchant_id, currency="TZS", pagination=PaginationParams(page=1, page_size=20)
    )

    assert total == 2
    # Newest first: the disbursement's wallet debit lands before the
    # collection's wallet credit.
    assert rows[0]["direction"] == "debit"
    assert Decimal(rows[0]["balance_after"]) == Decimal("700.00")
    assert rows[1]["direction"] == "credit"
    assert Decimal(rows[1]["balance_after"]) == Decimal("1000.00")


def test_list_wallet_ledger_paginates():
    client = FakeSupabaseClient()
    merchant_id = uuid.uuid4()

    for _ in range(5):
        post_collection_entries(
            client,
            transaction_id=uuid.uuid4(),
            merchant_id=merchant_id,
            gross_amount=Decimal("100.00"),
            fee_amount=Decimal(0),
            net_amount=Decimal("100.00"),
            currency="TZS",
        )

    page_1, total = list_wallet_ledger(
        client, merchant_id=merchant_id, currency="TZS", pagination=PaginationParams(page=1, page_size=2)
    )
    page_2, _ = list_wallet_ledger(
        client, merchant_id=merchant_id, currency="TZS", pagination=PaginationParams(page=2, page_size=2)
    )

    assert total == 5
    assert len(page_1) == 2
    assert len(page_2) == 2
    assert {row["id"] for row in page_1}.isdisjoint({row["id"] for row in page_2})


def test_list_wallet_ledger_scoped_to_one_merchant():
    client = FakeSupabaseClient()
    merchant_id = uuid.uuid4()
    other_merchant_id = uuid.uuid4()

    post_collection_entries(
        client,
        transaction_id=uuid.uuid4(),
        merchant_id=merchant_id,
        gross_amount=Decimal("500.00"),
        fee_amount=Decimal(0),
        net_amount=Decimal("500.00"),
        currency="TZS",
    )
    post_collection_entries(
        client,
        transaction_id=uuid.uuid4(),
        merchant_id=other_merchant_id,
        gross_amount=Decimal("999.00"),
        fee_amount=Decimal(0),
        net_amount=Decimal("999.00"),
        currency="TZS",
    )

    rows, total = list_wallet_ledger(
        client, merchant_id=merchant_id, currency="TZS", pagination=PaginationParams(page=1, page_size=20)
    )

    assert total == 1
    assert Decimal(rows[0]["balance_after"]) == Decimal("500.00")
