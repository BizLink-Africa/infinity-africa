"""Double-entry ledger posting for successful collections/disbursements.

Every posting here traces back to a transactions row and is enforced
balanced (debits == credits per transaction_id) by a deferred constraint
trigger in the database itself — see
supabase/migrations/20260814090013_ledger_entries.sql. This module just has
to get the debit/credit split right; the database refuses to commit if it
doesn't.
"""

import uuid
from decimal import Decimal

from supabase import Client

from app.core.errors import InsufficientBalanceError
from app.services.crud import execute_maybe_single, get_by_id, insert_row


def _get_or_create_ledger_account(
    client: Client,
    *,
    merchant_id: uuid.UUID | None,
    purpose: str,
    account_type: str,
    currency: str,
) -> uuid.UUID:
    query = client.table("ledger_accounts").select("id").eq("purpose", purpose).eq("currency", currency)
    query = query.eq("merchant_id", str(merchant_id)) if merchant_id else query.is_("merchant_id", "null")
    existing = execute_maybe_single(query.maybe_single())

    if existing:
        return uuid.UUID(existing["id"])

    try:
        row = insert_row(
            client,
            "ledger_accounts",
            {
                "merchant_id": str(merchant_id) if merchant_id else None,
                "name": _account_name(purpose, merchant_id),
                "account_type": account_type,
                "purpose": purpose,
                "currency": currency,
                "balance": "0",
            },
        )
    except Exception:
        # Lost a race with a concurrent get-or-create for the same account —
        # the unique index on ledger_accounts guarantees only one row can
        # exist, so re-fetch rather than fail the whole request.
        existing = execute_maybe_single(query.maybe_single())
        if existing:
            return uuid.UUID(existing["id"])
        raise

    return uuid.UUID(row["id"])


def _account_name(purpose: str, merchant_id: uuid.UUID | None) -> str:
    label = purpose.replace("_", " ").title()
    return f"{label} ({merchant_id})" if merchant_id else f"{label} (Platform)"


def _post_entries(client: Client, entries: list[dict]) -> None:
    """Posts a batch of ledger_entries and updates each account's cached
    balance atomically, via the post_ledger_entries Postgres function —
    supabase-py can't wrap multiple inserts/updates in one client-side
    transaction, and the deferred debits=credits trigger needs the whole
    batch to land in a single transaction to check correctly. The same
    function also rejects the whole batch, atomically, if it would take a
    merchant_wallet balance negative — see
    supabase/migrations/20260814140001_post_ledger_entries_balance_check.sql.
    """
    try:
        client.rpc("post_ledger_entries", {"p_entries": entries}).execute()
    except InsufficientBalanceError:
        raise
    except Exception as exc:
        if "INSUFFICIENT_BALANCE" in str(exc):
            raise InsufficientBalanceError("Insufficient balance for this operation") from exc
        raise


def get_wallet_balance(client: Client, *, merchant_id: uuid.UUID, currency: str) -> Decimal:
    """The merchant's current available balance — used to validate a
    disbursement up front, before even creating its row. Not itself the
    race-proof check (two concurrent reads can both see the same balance);
    that guarantee comes from post_ledger_entries' atomic check at actual
    deduction time, this is just for a fast, friendly rejection."""
    account_id = _get_or_create_ledger_account(
        client, merchant_id=merchant_id, purpose="merchant_wallet", account_type="liability", currency=currency
    )
    account = get_by_id(client, "ledger_accounts", account_id)
    return Decimal(str(account["balance"])) if account else Decimal(0)


def post_collection_entries(
    client: Client,
    *,
    transaction_id: uuid.UUID,
    merchant_id: uuid.UUID,
    gross_amount: Decimal,
    fee_amount: Decimal,
    net_amount: Decimal,
    currency: str,
) -> None:
    """A customer's payment lands in Infinity Africa's settlement account; the
    merchant's wallet balance grows by the net amount, and the fee becomes
    platform revenue. Debit (settlement_clearing) == credits (wallet + fee).
    """
    settlement_account_id = _get_or_create_ledger_account(
        client, merchant_id=None, purpose="settlement_clearing", account_type="asset", currency=currency
    )
    wallet_account_id = _get_or_create_ledger_account(
        client,
        merchant_id=merchant_id,
        purpose="merchant_wallet",
        account_type="liability",
        currency=currency,
    )

    entries = [
        {
            "transaction_id": str(transaction_id),
            "ledger_account_id": str(settlement_account_id),
            "direction": "debit",
            "amount": str(gross_amount),
            "currency": currency,
            "description": "Customer payment received into settlement",
        },
        {
            "transaction_id": str(transaction_id),
            "ledger_account_id": str(wallet_account_id),
            "direction": "credit",
            "amount": str(net_amount),
            "currency": currency,
            "description": "Merchant wallet credited (net of fee)",
        },
    ]

    if fee_amount > 0:
        revenue_account_id = _get_or_create_ledger_account(
            client, merchant_id=None, purpose="platform_revenue", account_type="revenue", currency=currency
        )
        entries.append(
            {
                "transaction_id": str(transaction_id),
                "ledger_account_id": str(revenue_account_id),
                "direction": "credit",
                "amount": str(fee_amount),
                "currency": currency,
                "description": "Platform fee revenue",
            }
        )

    _post_entries(client, entries)


def post_disbursement_entries(
    client: Client,
    *,
    transaction_id: uuid.UUID,
    merchant_id: uuid.UUID,
    amount: Decimal,
    currency: str,
) -> None:
    """A payout draws down the merchant's wallet and leaves Infinity Africa's
    settlement account. No disbursement fee modeled yet.
    """
    wallet_account_id = _get_or_create_ledger_account(
        client,
        merchant_id=merchant_id,
        purpose="merchant_wallet",
        account_type="liability",
        currency=currency,
    )
    settlement_account_id = _get_or_create_ledger_account(
        client, merchant_id=None, purpose="settlement_clearing", account_type="asset", currency=currency
    )

    entries = [
        {
            "transaction_id": str(transaction_id),
            "ledger_account_id": str(wallet_account_id),
            "direction": "debit",
            "amount": str(amount),
            "currency": currency,
            "description": "Merchant wallet debited for payout",
        },
        {
            "transaction_id": str(transaction_id),
            "ledger_account_id": str(settlement_account_id),
            "direction": "credit",
            "amount": str(amount),
            "currency": currency,
            "description": "Payout disbursed from settlement",
        },
    ]

    _post_entries(client, entries)


def post_refund_entry(
    client: Client,
    *,
    transaction_id: uuid.UUID,
    merchant_id: uuid.UUID,
    amount: Decimal,
    currency: str,
) -> None:
    """A refund draws down the merchant's wallet back out through
    settlement, same shape as post_disbursement_entries — the difference is
    only in which transactions row it's posted against (a new type='refund'
    row, not the original collection's, so each transaction_id's own
    debits/credits still balance independently). See
    app/services/disputes_service.py.update_refund_status()."""
    wallet_account_id = _get_or_create_ledger_account(
        client,
        merchant_id=merchant_id,
        purpose="merchant_wallet",
        account_type="liability",
        currency=currency,
    )
    settlement_account_id = _get_or_create_ledger_account(
        client, merchant_id=None, purpose="settlement_clearing", account_type="asset", currency=currency
    )

    entries = [
        {
            "transaction_id": str(transaction_id),
            "ledger_account_id": str(wallet_account_id),
            "direction": "debit",
            "amount": str(amount),
            "currency": currency,
            "description": "Merchant wallet debited for refund",
        },
        {
            "transaction_id": str(transaction_id),
            "ledger_account_id": str(settlement_account_id),
            "direction": "credit",
            "amount": str(amount),
            "currency": currency,
            "description": "Refund returned to customer via settlement",
        },
    ]

    _post_entries(client, entries)


def reverse_disbursement_entries(
    client: Client,
    *,
    transaction_id: uuid.UUID,
    merchant_id: uuid.UUID,
    amount: Decimal,
    currency: str,
) -> None:
    """Reverses a disbursement reservation that didn't go through: the
    opposite pair of entries against the *same* transaction_id, so the
    transaction nets to zero — exactly what a reserved-then-failed payout
    should look like in the ledger. Crediting the wallet back only
    increases its balance, so this never trips the insufficient-balance
    guard."""
    wallet_account_id = _get_or_create_ledger_account(
        client,
        merchant_id=merchant_id,
        purpose="merchant_wallet",
        account_type="liability",
        currency=currency,
    )
    settlement_account_id = _get_or_create_ledger_account(
        client, merchant_id=None, purpose="settlement_clearing", account_type="asset", currency=currency
    )

    entries = [
        {
            "transaction_id": str(transaction_id),
            "ledger_account_id": str(wallet_account_id),
            "direction": "credit",
            "amount": str(amount),
            "currency": currency,
            "description": "Merchant wallet reservation reversed (payout failed)",
        },
        {
            "transaction_id": str(transaction_id),
            "ledger_account_id": str(settlement_account_id),
            "direction": "debit",
            "amount": str(amount),
            "currency": currency,
            "description": "Settlement clearing reversed (payout failed)",
        },
    ]

    _post_entries(client, entries)
