"""Disbursement lifecycle: validate balance -> reserve -> call the provider
-> settle or reverse.

Mirrors app.services.collections' create-transaction-up-front shape, with
one addition disbursements need that collections don't: money has to
actually leave the merchant's available balance, and it must never go
negative. So instead of posting ledger entries only once a payout is
confirmed, a disbursement reserves its amount (debits the wallet) the
moment it starts processing — before the provider is even called — and
reverses that reservation (credits the wallet back) if the provider
declines. get_wallet_balance() is an up-front, friendly check; the
post_ledger_entries Postgres function (called via services/ledger.py) is
the atomic, race-proof one that actually enforces it.

A disbursement at or above settings.disbursement_approval_threshold is
held (status=PENDING, requires_approval=True) for a super admin to approve
before any of that happens — see the super-admin "high-value disbursement
approval queue". Rejecting one never reserved anything, so there's nothing
to reverse.
"""

import uuid
from decimal import Decimal

from supabase import Client

from app.config import get_settings
from app.core.errors import (
    ConflictError,
    InsufficientBalanceError,
    NotFoundError,
    SelcomAPIError,
    WithdrawalRestrictedError,
)
from app.core.references import generate_reference
from app.core.time import utc_now_iso
from app.schemas.enums import DisbursementMethod
from app.services.audit import write_audit_log
from app.services.crud import execute_maybe_single, get_by_id, insert_row, update_row
from app.services.ledger import (
    get_wallet_balance,
    post_disbursement_entries,
    reverse_disbursement_entries,
)
from app.services.notifications_service import notify_merchant
from app.services.selcom.client import get_selcom_client
from app.services.webhooks import enqueue_webhook_event


def _check_merchant_is_verified(client: Client, *, merchant_id: uuid.UUID) -> None:
    """Withdrawals are only for verified merchants — nothing enforced this
    before. onboarding.py's approval flow sets status="active" and
    kyc_status="verified" together (the moment a merchant becomes
    "APPROVED"); both are checked here since a merchant can be suspended
    again after verification without kyc_status changing. Enforced in both
    mock and live mode — mock mode mirrors live behavior, it isn't a
    verification-free sandbox."""
    merchant = get_by_id(client, "merchants", merchant_id)
    if not merchant or merchant.get("status") != "active" or merchant.get("kyc_status") != "verified":
        raise WithdrawalRestrictedError(
            "Withdrawals require a verified, active merchant account. Complete onboarding verification first."
        )


def _check_no_open_high_risk_alerts(client: Client, *, merchant_id: uuid.UUID) -> None:
    """Merchant-level withdrawal gate: blocks new withdrawal requests while
    the merchant has any HIGH/CRITICAL fraud alert still open, without
    touching balance-calculation math (a per-transaction fund freeze would
    need "available balance" semantics that don't exist today — see
    app/services/fraud_monitoring_service.py and the plan notes on this
    being the safe version of "restrict withdrawal of suspicious funds")."""
    rows = (
        client.table("fraud_alerts")
        .select("id")
        .eq("merchant_id", str(merchant_id))
        .in_("risk_level", ["HIGH", "CRITICAL"])
        .in_("status", ["OPEN", "UNDER_REVIEW", "DOCUMENTS_REQUESTED"])
        .execute()
    ).data or []
    if rows:
        raise WithdrawalRestrictedError(
            "Withdrawals are temporarily restricted while a high-risk transaction on this account is under review."
        )


async def execute_disbursement(
    client: Client,
    *,
    merchant_id: uuid.UUID,
    method: DisbursementMethod,
    amount: Decimal,
    currency: str,
    destination_name: str,
    destination_identifier: str,
    bank_name: str | None = None,
    network: str | None = None,
    description: str | None = None,
) -> dict:
    settings = get_settings()

    _check_merchant_is_verified(client, merchant_id=merchant_id)
    _check_no_open_high_risk_alerts(client, merchant_id=merchant_id)

    available = get_wallet_balance(client, merchant_id=merchant_id, currency=currency)
    if amount > available:
        raise InsufficientBalanceError(
            f"Insufficient balance: available {available} {currency}, requested {amount} {currency}"
        )

    requires_approval = amount >= settings.disbursement_approval_threshold

    metadata = {}
    if network:
        metadata["network"] = network
    if description:
        metadata["description"] = description

    disbursement = insert_row(
        client,
        "disbursements",
        {
            "merchant_id": str(merchant_id),
            "method": method.value,
            "amount": str(amount),
            "currency": currency,
            "destination_name": destination_name,
            "destination_identifier": destination_identifier,
            "bank_name": bank_name,
            "status": "PENDING",
            "requires_approval": requires_approval,
            "initiated_at": utc_now_iso(),
            "metadata": metadata,
        },
    )

    if requires_approval:
        return disbursement

    return await _reserve_and_run_disbursement_provider(client, disbursement)


async def approve_disbursement(
    client: Client, *, disbursement_id: uuid.UUID, approver_id: uuid.UUID
) -> dict:
    disbursement = get_by_id(client, "disbursements", disbursement_id)
    if not disbursement:
        raise NotFoundError("Disbursement not found")
    if disbursement["status"] != "PENDING" or not disbursement["requires_approval"]:
        raise ConflictError("This disbursement isn't awaiting approval")

    disbursement = update_row(
        client,
        "disbursements",
        disbursement_id,
        {"approved_by": str(approver_id), "approved_at": utc_now_iso()},
    )
    return await _reserve_and_run_disbursement_provider(client, disbursement)


def reject_disbursement(client: Client, *, disbursement_id: uuid.UUID, approver_id: uuid.UUID) -> dict:
    disbursement = get_by_id(client, "disbursements", disbursement_id)
    if not disbursement:
        raise NotFoundError("Disbursement not found")
    if disbursement["status"] != "PENDING" or not disbursement["requires_approval"]:
        raise ConflictError("This disbursement isn't awaiting approval")

    # Never reached reservation (that only happens once approved), so
    # there's nothing to reverse in the ledger.
    return update_row(
        client,
        "disbursements",
        disbursement_id,
        {
            "status": "FAILED",
            "approved_by": str(approver_id),
            "approved_at": utc_now_iso(),
            "completed_at": utc_now_iso(),
        },
    )


def _find_transaction_for_disbursement(client: Client, disbursement_id: uuid.UUID) -> dict | None:
    query = (
        client.table("transactions").select("*").eq("disbursement_id", str(disbursement_id)).maybe_single()
    )
    return execute_maybe_single(query)


def _stamp_response_fields(disbursement: dict, transaction: dict) -> dict:
    """Adds derived, non-column fields onto the dict returned to the API
    layer (see DisbursementResponse.transaction_reference/fee_amount/
    net_amount) — mirrors app/services/collections.py's identical
    collection["transaction_reference"] = ... pattern."""
    disbursement["transaction_reference"] = transaction["reference"]
    disbursement["fee_amount"] = transaction["fee_amount"]
    disbursement["net_amount"] = transaction["net_amount"]
    return disbursement


def _fail_and_reverse(
    client: Client,
    *,
    transaction_id: uuid.UUID,
    disbursement_id: uuid.UUID,
    merchant_id: uuid.UUID,
    amount: Decimal,
    currency: str,
    provider_reference: str | None,
    reason: str | None,
) -> dict:
    """Shared by every way a reservation can fail to become a successful
    payout: a clean provider rejection (result.status == "failed"), an
    outright provider-call exception (SelcomAPIError — a live timeout/HTTP
    error, which used to propagate unhandled and leave the wallet debited
    forever), and an async callback reporting failure after the fact.
    Reverses the reservation, marks both rows FAILED, audit-logs, notifies
    the merchant, and enqueues the outbound webhook."""
    reverse_disbursement_entries(
        client, transaction_id=transaction_id, merchant_id=merchant_id, amount=amount, currency=currency
    )
    update_row(
        client, "transactions", transaction_id, {"status": "reversed", "provider_reference": provider_reference}
    )
    disbursement = update_row(
        client,
        "disbursements",
        disbursement_id,
        {"status": "FAILED", "provider_reference": provider_reference, "completed_at": utc_now_iso()},
    )
    write_audit_log(
        client,
        action="disbursement.failed",
        resource_type="disbursement",
        resource_id=disbursement_id,
        actor_type="system",
        merchant_id=merchant_id,
        metadata={"reason": reason},
    )
    notify_merchant(
        client,
        merchant_id=merchant_id,
        notification_type="withdrawal_failed",
        title="Withdrawal failed",
        body=f"Your withdrawal of {amount} {currency} could not be completed."
        + (f" Reason: {reason}" if reason else ""),
        related_resource_type="disbursement",
        related_resource_id=disbursement_id,
    )
    enqueue_webhook_event(
        client,
        merchant_id=merchant_id,
        event_name="disbursement.failed",
        payload={"disbursement_id": str(disbursement_id), "reason": reason},
    )
    return disbursement


async def _reserve_and_run_disbursement_provider(client: Client, disbursement: dict) -> dict:
    merchant_id = uuid.UUID(disbursement["merchant_id"])
    amount = Decimal(str(disbursement["amount"]))
    currency = disbursement["currency"]
    disbursement_id = uuid.UUID(disbursement["id"])

    transaction = insert_row(
        client,
        "transactions",
        {
            "merchant_id": str(merchant_id),
            "reference": generate_reference("TXN"),
            "type": "disbursement",
            "method": disbursement["method"],
            "disbursement_id": disbursement["id"],
            "gross_amount": str(amount),
            "fee_amount": "0",
            "net_amount": str(amount),
            "currency": currency,
            "status": "processing",
        },
    )
    transaction_id = uuid.UUID(transaction["id"])

    disbursement = update_row(client, "disbursements", disbursement_id, {"status": "PROCESSING"})

    try:
        post_disbursement_entries(
            client, transaction_id=transaction_id, merchant_id=merchant_id, amount=amount, currency=currency
        )
    except InsufficientBalanceError:
        # A concurrent disbursement won the race between our up-front
        # get_wallet_balance() check and this atomic reservation. Nothing
        # was posted (the RPC's whole batch rolled back), so there's
        # nothing to reverse — just record the outcome.
        update_row(client, "transactions", transaction_id, {"status": "failed"})
        update_row(client, "disbursements", disbursement_id, {"status": "FAILED", "completed_at": utc_now_iso()})
        raise

    provider = get_selcom_client()
    metadata = disbursement.get("metadata") or {}

    try:
        result = await provider.initiate_disbursement(
            method=disbursement["method"],
            amount=amount,
            currency=currency,
            destination_identifier=disbursement["destination_identifier"],
            reference=generate_reference("DIS"),
            bank_name=disbursement.get("bank_name"),
            network=metadata.get("network"),
        )
    except SelcomAPIError as exc:
        # A live provider call that failed outright (timeout/connection/
        # non-2xx) — money was already reserved above, so this must be
        # reversed exactly like a clean rejection below, not left debited
        # with a stuck PROCESSING row and an unhandled 502.
        disbursement = _fail_and_reverse(
            client,
            transaction_id=transaction_id,
            disbursement_id=disbursement_id,
            merchant_id=merchant_id,
            amount=amount,
            currency=currency,
            provider_reference=None,
            reason=str(exc),
        )
        return _stamp_response_fields(disbursement, transaction)

    if result.status == "processing":
        # A real payout the provider hasn't resolved synchronously yet
        # (MockSelcomClient never returns this — it always settles in
        # one call). Leave PROCESSING; resolve_disbursement_from_callback
        # (the /v1/webhooks/selcom callback) is what resolves it later.
        disbursement = update_row(
            client, "disbursements", disbursement_id, {"provider_reference": result.provider_reference}
        )
        transaction = update_row(
            client, "transactions", transaction_id, {"provider_reference": result.provider_reference}
        )
        return _stamp_response_fields(disbursement, transaction)

    if result.status == "successful":
        update_row(
            client,
            "transactions",
            transaction_id,
            {"status": "successful", "provider_reference": result.provider_reference},
        )
        disbursement = update_row(
            client,
            "disbursements",
            disbursement_id,
            {"status": "SUCCESS", "provider_reference": result.provider_reference, "completed_at": utc_now_iso()},
        )
        enqueue_webhook_event(
            client,
            merchant_id=merchant_id,
            event_name="disbursement.success",
            payload={"disbursement_id": str(disbursement_id), "amount": str(amount), "currency": currency},
        )
        return _stamp_response_fields(disbursement, transaction)

    disbursement = _fail_and_reverse(
        client,
        transaction_id=transaction_id,
        disbursement_id=disbursement_id,
        merchant_id=merchant_id,
        amount=amount,
        currency=currency,
        provider_reference=result.provider_reference,
        reason=result.failure_reason,
    )
    return _stamp_response_fields(disbursement, transaction)


def resolve_disbursement_from_callback(
    client: Client,
    *,
    provider_reference: str,
    status: str,
    failure_reason: str | None,
) -> dict | None:
    """Resolves a disbursement left PROCESSING by an asynchronous provider
    callback — what the "processing" branch of
    _reserve_and_run_disbursement_provider above leaves ready for."""
    existing = execute_maybe_single(
        client.table("disbursements")
        .select("*")
        .eq("provider_reference", provider_reference)
        .eq("status", "PROCESSING")
        .maybe_single()
    )
    if not existing:
        return None

    disbursement_id = uuid.UUID(existing["id"])
    merchant_id = uuid.UUID(existing["merchant_id"])
    amount = Decimal(str(existing["amount"]))
    currency = existing["currency"]
    transaction = _find_transaction_for_disbursement(client, disbursement_id)
    transaction_id = uuid.UUID(transaction["id"])

    if status == "successful":
        transaction = update_row(client, "transactions", transaction_id, {"status": "successful"})
        disbursement = update_row(
            client, "disbursements", disbursement_id, {"status": "SUCCESS", "completed_at": utc_now_iso()}
        )
        enqueue_webhook_event(
            client,
            merchant_id=merchant_id,
            event_name="disbursement.success",
            payload={"disbursement_id": str(disbursement_id), "amount": str(amount), "currency": currency},
        )
        return _stamp_response_fields(disbursement, transaction)

    disbursement = _fail_and_reverse(
        client,
        transaction_id=transaction_id,
        disbursement_id=disbursement_id,
        merchant_id=merchant_id,
        amount=amount,
        currency=currency,
        provider_reference=existing.get("provider_reference"),
        reason=failure_reason,
    )
    return _stamp_response_fields(disbursement, transaction)


def reverse_successful_disbursement_from_callback(
    client: Client, *, provider_reference: str, reason: str | None
) -> dict | None:
    """Reverses an already-SUCCESS payout after Selcom reports it bounced
    after the fact (e.g. an invalid bank account only discovered once
    settlement was attempted) — credits the merchant's wallet back.
    REVERSED has existed as a DisbursementStatus since day one with no code
    path that ever set it; this is that path.

    Guarded by requiring status == "SUCCESS": a retried/duplicate
    'withdrawal.reversed' delivery finds the disbursement already REVERSED
    and no-ops, safe to call more than once for the same event (on top of
    the (provider, event_id) dedup already enforced one layer up in
    app/routers/webhooks.py)."""
    existing = execute_maybe_single(
        client.table("disbursements")
        .select("*")
        .eq("provider_reference", provider_reference)
        .eq("status", "SUCCESS")
        .maybe_single()
    )
    if not existing:
        return None

    disbursement_id = uuid.UUID(existing["id"])
    merchant_id = uuid.UUID(existing["merchant_id"])
    amount = Decimal(str(existing["amount"]))
    currency = existing["currency"]
    transaction = _find_transaction_for_disbursement(client, disbursement_id)
    transaction_id = uuid.UUID(transaction["id"])

    reverse_disbursement_entries(
        client, transaction_id=transaction_id, merchant_id=merchant_id, amount=amount, currency=currency
    )
    transaction = update_row(client, "transactions", transaction_id, {"status": "reversed"})
    disbursement = update_row(
        client, "disbursements", disbursement_id, {"status": "REVERSED", "completed_at": utc_now_iso()}
    )
    write_audit_log(
        client,
        action="disbursement.reversed",
        resource_type="disbursement",
        resource_id=disbursement_id,
        actor_type="system",
        merchant_id=merchant_id,
        metadata={"reason": reason},
    )
    notify_merchant(
        client,
        merchant_id=merchant_id,
        notification_type="withdrawal_reversed",
        title="Withdrawal reversed",
        body=f"Your withdrawal of {amount} {currency} was reversed by the provider after settlement."
        + (f" Reason: {reason}" if reason else ""),
        related_resource_type="disbursement",
        related_resource_id=disbursement_id,
    )
    enqueue_webhook_event(
        client,
        merchant_id=merchant_id,
        event_name="disbursement.reversed",
        payload={"disbursement_id": str(disbursement_id), "reason": reason},
    )
    return _stamp_response_fields(disbursement, transaction)
