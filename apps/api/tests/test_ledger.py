"""app.services.ledger — balance_before/balance_after/direction capture on
both ledger_entries (authoritative, immutable) and transactions
(denormalized, for fast display) — see supabase/migrations/20260828*.
"""

import uuid
from decimal import Decimal

from app.core.errors import InsufficientBalanceError
from app.services.crud import insert_row
from app.services.ledger import (
    get_wallet_balance,
    list_wallet_ledger,
    post_collection_entries,
    post_disbursement_entries,
    post_refund_entry,
    reverse_collection_entries,
    reverse_disbursement_entries,
)
from tests.factories import create_merchant


class _Pagination:
    """Minimal stand-in for app.core.pagination.PaginationParams — only
    .start/.end are read by list_wallet_ledger."""

    def __init__(self, start: int = 0, end: int = 49):
        self.start = start
        self.end = end


def _merchant(fake_client) -> uuid.UUID:
    return uuid.UUID(create_merchant(fake_client)["id"])


def _seed_transaction(fake_client, merchant_id: uuid.UUID, *, gross: str, fee: str, net: str, type_: str = "collection") -> uuid.UUID:
    row = insert_row(
        fake_client,
        "transactions",
        {
            "merchant_id": str(merchant_id),
            "reference": f"TXN-{uuid.uuid4().hex[:8]}",
            "type": type_,
            "method": "STK_PUSH" if type_ == "collection" else "SELCOM_PESA",
            "gross_amount": gross,
            "fee_amount": fee,
            "net_amount": net,
            "currency": "TZS",
            "status": "processing",
        },
    )
    return uuid.UUID(row["id"])


def _transaction_row(fake_client, transaction_id: uuid.UUID) -> dict:
    return next(r for r in fake_client.table("transactions")._table.rows if r["id"] == str(transaction_id))


def test_collection_posting_stores_opening_and_closing_balance_on_the_transaction(fake_client):
    merchant_id = _merchant(fake_client)
    transaction_id = _seed_transaction(fake_client, merchant_id, gross="1000", fee="15", net="985")

    post_collection_entries(
        fake_client,
        transaction_id=transaction_id,
        merchant_id=merchant_id,
        gross_amount=Decimal(1000),
        fee_amount=Decimal(15),
        net_amount=Decimal(985),
        currency="TZS",
    )

    row = _transaction_row(fake_client, transaction_id)
    assert Decimal(str(row["balance_before"])) == Decimal(0)
    assert Decimal(str(row["balance_after"])) == Decimal(985)
    assert row["direction"] == "credit"


def test_collection_fee_is_visible_and_net_is_gross_minus_fee(fake_client):
    merchant_id = _merchant(fake_client)
    transaction_id = _seed_transaction(fake_client, merchant_id, gross="1000", fee="15", net="985")

    post_collection_entries(
        fake_client,
        transaction_id=transaction_id,
        merchant_id=merchant_id,
        gross_amount=Decimal(1000),
        fee_amount=Decimal(15),
        net_amount=Decimal(985),
        currency="TZS",
    )

    row = _transaction_row(fake_client, transaction_id)
    assert Decimal(str(row["fee_amount"])) == Decimal(15)
    assert Decimal(str(row["net_amount"])) == Decimal(str(row["gross_amount"])) - Decimal(str(row["fee_amount"]))


def test_second_collection_opening_balance_matches_first_collections_closing_balance(fake_client):
    merchant_id = _merchant(fake_client)
    txn_1 = _seed_transaction(fake_client, merchant_id, gross="1000", fee="0", net="1000")
    post_collection_entries(
        fake_client, transaction_id=txn_1, merchant_id=merchant_id,
        gross_amount=Decimal(1000), fee_amount=Decimal(0), net_amount=Decimal(1000), currency="TZS",
    )

    txn_2 = _seed_transaction(fake_client, merchant_id, gross="500", fee="0", net="500")
    post_collection_entries(
        fake_client, transaction_id=txn_2, merchant_id=merchant_id,
        gross_amount=Decimal(500), fee_amount=Decimal(0), net_amount=Decimal(500), currency="TZS",
    )

    row_1 = _transaction_row(fake_client, txn_1)
    row_2 = _transaction_row(fake_client, txn_2)
    assert Decimal(str(row_2["balance_before"])) == Decimal(str(row_1["balance_after"])) == Decimal(1000)
    assert Decimal(str(row_2["balance_after"])) == Decimal(1500)


def test_disbursement_reservation_stores_debit_direction_and_correct_balances(fake_client):
    merchant_id = _merchant(fake_client)
    funding_txn = _seed_transaction(fake_client, merchant_id, gross="1000", fee="0", net="1000")
    post_collection_entries(
        fake_client, transaction_id=funding_txn, merchant_id=merchant_id,
        gross_amount=Decimal(1000), fee_amount=Decimal(0), net_amount=Decimal(1000), currency="TZS",
    )

    payout_txn = _seed_transaction(
        fake_client, merchant_id, gross="600", fee="10", net="590", type_="disbursement"
    )
    post_disbursement_entries(
        fake_client,
        transaction_id=payout_txn,
        merchant_id=merchant_id,
        amount=Decimal(590),
        fee_amount=Decimal(10),
        currency="TZS",
    )

    row = _transaction_row(fake_client, payout_txn)
    assert row["direction"] == "debit"
    assert Decimal(str(row["balance_before"])) == Decimal(1000)
    assert Decimal(str(row["balance_after"])) == Decimal(400)  # 1000 - (590 + 10)


def test_disbursement_reservation_rejected_when_it_would_take_the_wallet_negative(fake_client):
    merchant_id = _merchant(fake_client)
    payout_txn = _seed_transaction(fake_client, merchant_id, gross="600", fee="0", net="600", type_="disbursement")

    try:
        post_disbursement_entries(
            fake_client, transaction_id=payout_txn, merchant_id=merchant_id,
            amount=Decimal(600), fee_amount=Decimal(0), currency="TZS",
        )
        assert False, "expected InsufficientBalanceError"
    except InsufficientBalanceError:
        pass

    # Rejected atomically — no snapshot should have been written.
    row = _transaction_row(fake_client, payout_txn)
    assert row.get("balance_before") is None
    assert row.get("balance_after") is None


def test_reversing_a_collection_updates_the_transaction_to_the_post_reversal_balance(fake_client):
    merchant_id = _merchant(fake_client)
    transaction_id = _seed_transaction(fake_client, merchant_id, gross="1000", fee="15", net="985")
    post_collection_entries(
        fake_client, transaction_id=transaction_id, merchant_id=merchant_id,
        gross_amount=Decimal(1000), fee_amount=Decimal(15), net_amount=Decimal(985), currency="TZS",
    )

    reverse_collection_entries(
        fake_client, transaction_id=transaction_id, merchant_id=merchant_id,
        gross_amount=Decimal(1000), fee_amount=Decimal(15), net_amount=Decimal(985), currency="TZS",
    )

    row = _transaction_row(fake_client, transaction_id)
    # The reversal is a debit of net_amount off the wallet — opening balance
    # for *this* posting is where the wallet stood right before the
    # reversal (985, post-collection), closing balance is back to 0.
    assert row["direction"] == "debit"
    assert Decimal(str(row["balance_before"])) == Decimal(985)
    assert Decimal(str(row["balance_after"])) == Decimal(0)


def test_reversing_a_disbursement_credits_the_reservation_back(fake_client):
    merchant_id = _merchant(fake_client)
    funding_txn = _seed_transaction(fake_client, merchant_id, gross="1000", fee="0", net="1000")
    post_collection_entries(
        fake_client, transaction_id=funding_txn, merchant_id=merchant_id,
        gross_amount=Decimal(1000), fee_amount=Decimal(0), net_amount=Decimal(1000), currency="TZS",
    )
    payout_txn = _seed_transaction(fake_client, merchant_id, gross="600", fee="10", net="590", type_="disbursement")
    post_disbursement_entries(
        fake_client, transaction_id=payout_txn, merchant_id=merchant_id,
        amount=Decimal(590), fee_amount=Decimal(10), currency="TZS",
    )

    reverse_disbursement_entries(
        fake_client, transaction_id=payout_txn, merchant_id=merchant_id,
        amount=Decimal(590), fee_amount=Decimal(10), currency="TZS",
    )

    row = _transaction_row(fake_client, payout_txn)
    assert row["direction"] == "credit"
    assert Decimal(str(row["balance_before"])) == Decimal(400)
    assert Decimal(str(row["balance_after"])) == Decimal(1000)
    assert get_wallet_balance(fake_client, merchant_id=merchant_id, currency="TZS") == Decimal(1000)


def test_refund_debits_the_wallet_and_records_the_snapshot(fake_client):
    merchant_id = _merchant(fake_client)
    funding_txn = _seed_transaction(fake_client, merchant_id, gross="1000", fee="0", net="1000")
    post_collection_entries(
        fake_client, transaction_id=funding_txn, merchant_id=merchant_id,
        gross_amount=Decimal(1000), fee_amount=Decimal(0), net_amount=Decimal(1000), currency="TZS",
    )
    refund_txn = _seed_transaction(fake_client, merchant_id, gross="200", fee="0", net="200", type_="refund")

    post_refund_entry(
        fake_client, transaction_id=refund_txn, merchant_id=merchant_id, amount=Decimal(200), currency="TZS",
    )

    row = _transaction_row(fake_client, refund_txn)
    assert row["direction"] == "debit"
    assert Decimal(str(row["balance_before"])) == Decimal(1000)
    assert Decimal(str(row["balance_after"])) == Decimal(800)


def test_old_ledger_entries_without_a_balance_snapshot_do_not_crash_the_wallet_ledger_list(fake_client):
    """Simulates a pre-migration row: seeded directly, no balance_before/
    after — list_wallet_ledger must fall back to its own deterministic
    running-balance replay rather than error or fabricate a wrong number."""
    merchant_id = _merchant(fake_client)
    account = fake_client.seed(
        "ledger_accounts",
        {
            "merchant_id": str(merchant_id),
            "name": "Merchant Wallet",
            "account_type": "liability",
            "purpose": "merchant_wallet",
            "currency": "TZS",
            "balance": "500",
        },
    )
    transaction_id = _seed_transaction(fake_client, merchant_id, gross="500", fee="0", net="500")
    fake_client.seed(
        "ledger_entries",
        {
            "transaction_id": str(transaction_id),
            "ledger_account_id": account["id"],
            "direction": "credit",
            "amount": "500",
            "currency": "TZS",
            "description": "Pre-migration entry, no balance snapshot",
            # balance_before/balance_after deliberately omitted.
        },
    )

    entries, total = list_wallet_ledger(
        fake_client, merchant_id=merchant_id, currency="TZS", pagination=_Pagination()
    )

    assert total == 1
    assert entries[0]["balance_before"] == "0"
    assert entries[0]["balance_after"] == "500"


def test_wallet_ledger_list_includes_the_transaction_id_for_traceability(fake_client):
    merchant_id = _merchant(fake_client)
    transaction_id = _seed_transaction(fake_client, merchant_id, gross="1000", fee="0", net="1000")
    post_collection_entries(
        fake_client, transaction_id=transaction_id, merchant_id=merchant_id,
        gross_amount=Decimal(1000), fee_amount=Decimal(0), net_amount=Decimal(1000), currency="TZS",
    )

    entries, _total = list_wallet_ledger(
        fake_client, merchant_id=merchant_id, currency="TZS", pagination=_Pagination()
    )

    wallet_entry = next(e for e in entries if e["direction"] == "credit")
    assert wallet_entry["transaction_id"] == str(transaction_id)
    assert wallet_entry["balance_before"] == "0"
    assert wallet_entry["balance_after"] == "1000"
