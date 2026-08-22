"""Withdrawal lifecycle: quote a fee, validate balance, freeze the fee
snapshot, wait for Super Admin approval, then (only on approval) reserve
funds and call the provider -> settle or reverse.

Mirrors app.services.collections' create-transaction-up-front shape, with
two additions withdrawals need that collections don't: money has to
actually leave the merchant's available balance (reserved atomically, never
allowed to go negative), and — as of this module's pricing/approval
redesign — no withdrawal may ever reach the provider without a Super Admin
explicitly approving it first, regardless of amount. get_wallet_balance()
is an up-front, friendly check; the post_ledger_entries Postgres function
(called via services/ledger.py) is the atomic, race-proof one that actually
enforces both the no-negative-balance rule and (indirectly) the
approval-before-Selcom rule, since reservation only ever happens from
approve_disbursement.

Every withdrawal is created PENDING_ADMIN_APPROVAL with its fee breakdown
(see app/services/withdrawals/fee_calculator.py) frozen onto the row —
approving it later uses that stored snapshot, never recalculates. Rejecting
one never reserved anything, so there's nothing to reverse.
"""

import logging
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
from app.core.phone import InvalidPhoneNumberError, normalize_tz_phone
from app.core.references import generate_reference
from app.core.time import utc_now_iso
from app.schemas.enums import DestinationCode, DisbursementMethod, NotificationType
from app.schemas.withdrawals import FeeBreakdown
from app.services.audit import write_audit_log
from app.services.crud import execute_maybe_single, get_by_id, insert_row, update_row
from app.services.ledger import (
    get_wallet_balance,
    post_disbursement_entries,
    reverse_disbursement_entries,
)
from app.services.notifications_service import notify_merchant
from app.services.selcom_business.client import get_selcom_business_client
from app.services.webhooks import enqueue_webhook_event
from app.services.withdrawals.fee_calculator import calculate_withdrawal_fee

logger = logging.getLogger("infinity.disbursements")

_AWAITING_ADMIN_STATUSES = ("PENDING_ADMIN_APPROVAL", "INFO_REQUESTED")


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


def _check_pilot_amount_limit(amount: Decimal) -> None:
    """Controlled production pilot guardrail
    (docs/withdrawal-production-pilot-checklist.md) — an extra, temporary
    cap on top of the platform's normal withdrawal validation, active only
    while WITHDRAWAL_PILOT_MODE=true. Not a permanent business rule; turn
    the env var off once the pilot is reconciled and approved to expand."""
    settings = get_settings()
    if not settings.withdrawal_pilot_mode:
        return
    if amount > settings.withdrawal_pilot_max_amount_tzs:
        raise WithdrawalRestrictedError(
            f"Withdrawals are currently limited to {settings.withdrawal_pilot_max_amount_tzs} TZS "
            "during the production pilot. Contact Infinity Africa if you need a higher limit."
        )


def quote_withdrawal_fee(
    client: Client,
    *,
    merchant_id: uuid.UUID,
    amount: Decimal,
    method: DisbursementMethod,
    destination_code: DestinationCode,
) -> FeeBreakdown:
    """POST /v1/merchant/withdrawals/quote — read-only, no side effects.
    Never touches disbursements/ledger/Selcom; see
    app/routers/merchant_portal.py."""
    return calculate_withdrawal_fee(
        client, merchant_id=merchant_id, amount=amount, channel=method, destination_code=destination_code
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
    destination_code: DestinationCode,
    bank_name: str | None = None,
    network: str | None = None,
    description: str | None = None,
) -> dict:
    """Every withdrawal request — any amount, any channel — lands here and
    always ends up PENDING_ADMIN_APPROVAL. Selcom is never called from this
    path; only approve_disbursement (below) ever reaches the provider."""
    _check_merchant_is_verified(client, merchant_id=merchant_id)
    _check_no_open_high_risk_alerts(client, merchant_id=merchant_id)
    _check_pilot_amount_limit(amount)

    breakdown = calculate_withdrawal_fee(
        client, merchant_id=merchant_id, amount=amount, channel=method, destination_code=destination_code
    )

    available = get_wallet_balance(client, merchant_id=merchant_id, currency=currency)
    if breakdown.total_reserved_amount > available:
        raise InsufficientBalanceError(
            f"Insufficient balance: available {available} {currency}, "
            f"requested {breakdown.total_reserved_amount} {currency} (amount + fees)"
        )

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
            "destination_code": breakdown.destination_code,
            "bank_name": bank_name,
            "status": "PENDING_ADMIN_APPROVAL",
            "requires_approval": True,
            "initiated_at": utc_now_iso(),
            "metadata": metadata,
            "processor_charge": str(breakdown.processor_charge),
            "infinity_fee": str(breakdown.infinity_fee),
            "percentage_fee_component": str(breakdown.percentage_fee),
            "flat_fee_component": str(breakdown.flat_fee),
            "total_charges": str(breakdown.total_charges),
            "total_reserved_amount": str(breakdown.total_reserved_amount),
            "recipient_net_amount": str(breakdown.recipient_net_amount),
            "pricing_rule_id": str(breakdown.pricing_rule_id) if breakdown.pricing_rule_id else None,
            "pricing_snapshot_json": breakdown.model_dump(mode="json"),
        },
    )
    return disbursement


async def approve_disbursement(
    client: Client, *, disbursement_id: uuid.UUID, approver_id: uuid.UUID
) -> dict:
    disbursement = get_by_id(client, "disbursements", disbursement_id)
    if not disbursement:
        raise NotFoundError("Disbursement not found")
    if disbursement["status"] != "PENDING_ADMIN_APPROVAL":
        raise ConflictError("This withdrawal isn't awaiting approval")

    disbursement = update_row(
        client,
        "disbursements",
        disbursement_id,
        {"approved_by": str(approver_id), "approved_at": utc_now_iso()},
    )
    return await _reserve_and_run_disbursement_provider(client, disbursement)


def reject_disbursement(
    client: Client, *, disbursement_id: uuid.UUID, approver_id: uuid.UUID, rejection_reason: str
) -> dict:
    disbursement = get_by_id(client, "disbursements", disbursement_id)
    if not disbursement:
        raise NotFoundError("Disbursement not found")
    if disbursement["status"] not in _AWAITING_ADMIN_STATUSES:
        raise ConflictError("This withdrawal isn't awaiting approval")

    # Never reached reservation (that only happens once approved), so
    # there's nothing to reverse in the ledger.
    disbursement = update_row(
        client,
        "disbursements",
        disbursement_id,
        {
            "status": "REJECTED",
            "rejected_by": str(approver_id),
            "rejected_at": utc_now_iso(),
            "rejection_reason": rejection_reason,
            "completed_at": utc_now_iso(),
        },
    )
    # Same notify_merchant the failed/info-requested paths already have —
    # previously missing here entirely, so a rejected withdrawal only ever
    # showed a bare "Rejected" status with no visible reason unless the
    # merchant specifically opened the withdrawal's own detail view.
    notify_merchant(
        client,
        merchant_id=uuid.UUID(disbursement["merchant_id"]),
        notification_type=NotificationType.WITHDRAWAL_REJECTED,
        title="Withdrawal rejected",
        body=rejection_reason,
        related_resource_type="disbursement",
        related_resource_id=disbursement_id,
    )
    return disbursement


def request_more_info(
    client: Client,
    *,
    disbursement_id: uuid.UUID,
    admin_id: uuid.UUID,
    message: str,
    requested_documents: list[str],
) -> dict:
    disbursement = get_by_id(client, "disbursements", disbursement_id)
    if not disbursement:
        raise NotFoundError("Disbursement not found")
    if disbursement["status"] != "PENDING_ADMIN_APPROVAL":
        raise ConflictError("This withdrawal isn't awaiting approval")

    disbursement = update_row(
        client,
        "disbursements",
        disbursement_id,
        {
            "status": "INFO_REQUESTED",
            "admin_status_reason": message,
            "metadata": {**(disbursement.get("metadata") or {}), "requested_documents": requested_documents},
        },
    )
    notify_merchant(
        client,
        merchant_id=uuid.UUID(disbursement["merchant_id"]),
        notification_type=NotificationType.WITHDRAWAL_INFO_REQUESTED,
        title="More information needed for your withdrawal",
        body=message,
        related_resource_type="disbursement",
        related_resource_id=disbursement_id,
    )
    return disbursement


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
    fee_amount: Decimal,
    currency: str,
    provider_reference: str | None,
    reason: str | None,
    raw_response: dict | None = None,
) -> dict:
    """Shared by every way a reservation can fail to become a successful
    payout: a clean provider rejection (result.status == "failed"), an
    outright provider-call exception (SelcomAPIError — a live timeout/HTTP
    error, which used to propagate unhandled and leave the wallet debited
    forever), and an async callback reporting failure after the fact.
    Reverses the reservation (full amount + fee), marks both rows FAILED,
    audit-logs, notifies the merchant, and enqueues the outbound webhook."""
    reverse_disbursement_entries(
        client,
        transaction_id=transaction_id,
        merchant_id=merchant_id,
        amount=amount,
        fee_amount=fee_amount,
        currency=currency,
    )
    update_row(
        client, "transactions", transaction_id, {"status": "reversed", "provider_reference": provider_reference}
    )
    update_data = {"status": "FAILED", "provider_reference": provider_reference, "completed_at": utc_now_iso()}
    if reason is not None:
        # Same column the "ambiguous"/BLOCKED_IP_WHITELIST paths already use
        # for "why is this disbursement in its current state" — previously
        # only reached write_audit_log/notify_merchant, never persisted onto
        # the row itself, so the merchant/admin dashboards had no way to
        # show a failed withdrawal's actual reason.
        update_data["admin_status_reason"] = reason
    if raw_response is not None:
        update_data["selcom_raw_response"] = raw_response
    try:
        disbursement = update_row(client, "disbursements", disbursement_id, update_data)
    except Exception:
        # The ledger reversal above already ran and cannot be undone — a
        # disbursement reaching its terminal FAILED status must never be
        # blocked by a problem saving a single extra field (e.g. schema
        # drift like a column that hasn't been migrated onto this database
        # yet). Retry without selcom_raw_response rather than leave the row
        # stuck at its pre-failure status with no way to resolve it.
        if "selcom_raw_response" not in update_data:
            raise
        logger.exception(
            "disbursement_selcom_raw_response_save_failed disbursement_id=%s — retrying without it",
            disbursement_id,
        )
        del update_data["selcom_raw_response"]
        disbursement = update_row(client, "disbursements", disbursement_id, update_data)
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
        notification_type=NotificationType.WITHDRAWAL_FAILED,
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


def _block_ip_whitelist(
    client: Client, *, disbursement_id: uuid.UUID, merchant_id: uuid.UUID, reason: str
) -> dict:
    """Selcom rejected the call as coming from a non-whitelisted IP (HTTP
    403 — see docs/selcom-live-go-live.md's static-outbound-IP
    requirement). Funds stay reserved; this needs an operator to fix the
    whitelisting and then retry via POST .../refresh-status or a fresh
    approval, not an automatic reversal — the withdrawal itself is still
    perfectly valid, only this backend's network access is the problem."""
    disbursement = update_row(
        client,
        "disbursements",
        disbursement_id,
        {"status": "BLOCKED_IP_WHITELIST", "admin_status_reason": reason},
    )
    write_audit_log(
        client,
        action="disbursement.blocked_ip_whitelist",
        resource_type="disbursement",
        resource_id=disbursement_id,
        actor_type="system",
        merchant_id=merchant_id,
        metadata={"reason": reason},
    )
    return disbursement


async def _reserve_and_run_disbursement_provider(client: Client, disbursement: dict) -> dict:
    merchant_id = uuid.UUID(disbursement["merchant_id"])
    amount = Decimal(str(disbursement["recipient_net_amount"] or disbursement["amount"]))
    fee_amount = Decimal(str(disbursement.get("total_charges") or "0"))
    total_reserved = Decimal(str(disbursement.get("total_reserved_amount") or disbursement["amount"]))
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
            "gross_amount": str(total_reserved),
            "fee_amount": str(fee_amount),
            "net_amount": str(amount),
            "currency": currency,
            "status": "processing",
        },
    )
    transaction_id = uuid.UUID(transaction["id"])

    disbursement = update_row(client, "disbursements", disbursement_id, {"status": "PROCESSING"})

    try:
        post_disbursement_entries(
            client,
            transaction_id=transaction_id,
            merchant_id=merchant_id,
            amount=amount,
            fee_amount=fee_amount,
            currency=currency,
        )
    except InsufficientBalanceError:
        # A concurrent withdrawal won the race between our up-front
        # get_wallet_balance() check and this atomic reservation. Nothing
        # was posted (the RPC's whole batch rolled back), so there's
        # nothing to reverse — just record the outcome.
        update_row(client, "transactions", transaction_id, {"status": "failed"})
        update_row(client, "disbursements", disbursement_id, {"status": "FAILED", "completed_at": utc_now_iso()})
        raise

    provider = get_selcom_business_client()

    try:
        recipient_account = disbursement["destination_identifier"]
        if disbursement["method"] != "BANK_ACCOUNT":
            # Normalized once already at submission — normalized again here
            # as defense-in-depth per the requirement, since data can't be
            # assumed immutable between submission and approval.
            recipient_account = normalize_tz_phone(recipient_account)
    except InvalidPhoneNumberError as exc:
        # Funds stay reserved — this is a data-integrity anomaly needing a
        # human look, not a payout failure to reverse.
        disbursement = update_row(
            client,
            "disbursements",
            disbursement_id,
            {
                "status": "NEEDS_ADMIN_ATTENTION",
                "admin_status_reason": f"Recipient account failed re-normalization at approval time: {exc}",
            },
        )
        return _stamp_response_fields(disbursement, transaction)

    trans_id = generate_reference("DIS")

    try:
        result = await provider.process_transaction(
            trans_id=trans_id,
            recipient_fi_code=disbursement.get("destination_code") or disbursement["method"],
            recipient_account=recipient_account,
            recipient_name=disbursement.get("destination_name") or "",
            amount=str(amount),
            purpose="withdrawal",
        )
    except SelcomAPIError as exc:
        if exc.is_ip_whitelist_error:
            # Funds stay reserved deliberately — see _block_ip_whitelist.
            disbursement = _block_ip_whitelist(
                client, disbursement_id=disbursement_id, merchant_id=merchant_id, reason=str(exc)
            )
            return _stamp_response_fields(disbursement, transaction)

        # A live provider call that failed outright (timeout/connection/
        # non-2xx, not a whitelist rejection) — money was already reserved
        # above, so this must be reversed exactly like a clean rejection
        # below, not left debited with a stuck PROCESSING row.
        disbursement = _fail_and_reverse(
            client,
            transaction_id=transaction_id,
            disbursement_id=disbursement_id,
            merchant_id=merchant_id,
            amount=amount,
            fee_amount=fee_amount,
            currency=currency,
            provider_reference=None,
            reason=str(exc),
            raw_response=exc.provider_response_body,
        )
        return _stamp_response_fields(disbursement, transaction)

    if result.status == "processing":
        # A real payout the provider hasn't resolved synchronously yet
        # (MockSelcomBusinessClient never returns this — it always settles
        # in one call). Leave PROCESSING; an admin-triggered
        # refresh_disbursement_status is what resolves it later (the
        # Business API is request/response + a query endpoint, not a
        # webhook-driven flow).
        disbursement = update_row(
            client,
            "disbursements",
            disbursement_id,
            {
                "provider_reference": trans_id,
                "selcom_trans_id": result.transaction_id,
                "selcom_raw_response": result.raw_response,
            },
        )
        transaction = update_row(client, "transactions", transaction_id, {"provider_reference": trans_id})
        return _stamp_response_fields(disbursement, transaction)

    if result.status == "ambiguous":
        # Selcom's response couldn't be confidently resolved to success or
        # failure — funds stay reserved (not reversed: we don't yet know
        # the payout didn't happen) pending manual reconciliation.
        disbursement = update_row(
            client,
            "disbursements",
            disbursement_id,
            {
                "status": "NEEDS_RECONCILIATION",
                "provider_reference": trans_id,
                "selcom_trans_id": result.transaction_id,
                "admin_status_reason": result.failure_reason,
                "selcom_raw_response": result.raw_response,
            },
        )
        transaction = update_row(client, "transactions", transaction_id, {"provider_reference": trans_id})
        return _stamp_response_fields(disbursement, transaction)

    if result.status == "successful":
        update_row(
            client,
            "transactions",
            transaction_id,
            {"status": "successful", "provider_reference": trans_id},
        )
        disbursement = update_row(
            client,
            "disbursements",
            disbursement_id,
            {
                "status": "SUCCESS",
                "provider_reference": trans_id,
                "selcom_trans_id": result.transaction_id,
                "selcom_receipt": result.receipt,
                "selcom_status": result.raw_status,
                "selcom_raw_response": result.raw_response,
                "completed_at": utc_now_iso(),
            },
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
        fee_amount=fee_amount,
        currency=currency,
        provider_reference=trans_id,
        reason=result.failure_reason,
        raw_response=result.raw_response,
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

    return _resolve_processing_disbursement(client, existing, status=status, failure_reason=failure_reason)


def _resolve_processing_disbursement(
    client: Client,
    existing: dict,
    *,
    status: str,
    failure_reason: str | None,
    receipt: str | None = None,
    raw_status: str | None = None,
    raw_response: dict | None = None,
) -> dict:
    """receipt/raw_status/raw_response are only ever populated when this is
    called from refresh_disbursement_status (a real SelcomBusinessResult
    from query_transaction) — resolve_disbursement_from_callback above only
    has a bare status string from the manual test-webhook endpoint, with no
    parsed provider result to enrich these from."""
    disbursement_id = uuid.UUID(existing["id"])
    merchant_id = uuid.UUID(existing["merchant_id"])
    amount = Decimal(str(existing.get("recipient_net_amount") or existing["amount"]))
    fee_amount = Decimal(str(existing.get("total_charges") or "0"))
    currency = existing["currency"]
    transaction = _find_transaction_for_disbursement(client, disbursement_id)
    transaction_id = uuid.UUID(transaction["id"])

    if status == "successful":
        transaction = update_row(client, "transactions", transaction_id, {"status": "successful"})
        update_data = {"status": "SUCCESS", "completed_at": utc_now_iso()}
        if receipt is not None:
            update_data["selcom_receipt"] = receipt
        if raw_status is not None:
            update_data["selcom_status"] = raw_status
        if raw_response is not None:
            update_data["selcom_raw_response"] = raw_response
        disbursement = update_row(client, "disbursements", disbursement_id, update_data)
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
        fee_amount=fee_amount,
        currency=currency,
        provider_reference=existing.get("provider_reference"),
        reason=failure_reason,
        raw_response=raw_response,
    )
    return _stamp_response_fields(disbursement, transaction)


async def refresh_disbursement_status(client: Client, *, disbursement_id: uuid.UUID) -> dict:
    """Admin-triggered manual refresh for a withdrawal stuck PROCESSING or
    NEEDS_RECONCILIATION after approval — never called automatically by any
    background worker (none exists in this codebase), and never reachable
    before approval, since only an approved (and therefore already-reserved)
    withdrawal has a provider_reference to check."""
    disbursement = get_by_id(client, "disbursements", disbursement_id)
    if not disbursement:
        raise NotFoundError("Disbursement not found")
    if disbursement["status"] not in ("PROCESSING", "NEEDS_RECONCILIATION"):
        raise ConflictError("This withdrawal isn't awaiting a status refresh")
    if not disbursement.get("provider_reference"):
        raise ConflictError("This withdrawal has no provider reference to check yet")

    provider = get_selcom_business_client()
    result = await provider.query_transaction(trans_id=disbursement["provider_reference"])

    if result.status == "processing":
        return disbursement
    if result.status == "ambiguous":
        return update_row(
            client,
            "disbursements",
            disbursement_id,
            {
                "status": "NEEDS_RECONCILIATION",
                "admin_status_reason": result.failure_reason,
                "selcom_raw_response": result.raw_response,
            },
        )
    return _resolve_processing_disbursement(
        client,
        disbursement,
        status=result.status,
        failure_reason=result.failure_reason,
        receipt=result.receipt,
        raw_status=result.raw_status,
        raw_response=result.raw_response,
    )


async def reconcile_pending_disbursements(client: Client) -> dict:
    """POST /v1/admin/withdrawals/reconcile-pending — admin-triggered batch
    refresh over every stuck PROCESSING/NEEDS_RECONCILIATION withdrawal.
    Not a cron/background job (none exists in this codebase, and the
    business rule against unattended Selcom calls before approval doesn't
    apply here — these are all already-approved withdrawals) — only ever
    runs when a Super Admin clicks the button."""
    rows = (
        client.table("disbursements")
        .select("id, status")
        .in_("status", ["PROCESSING", "NEEDS_RECONCILIATION"])
        .execute()
    ).data or []

    resolved = 0
    still_pending = 0
    for row in rows:
        outcome = await refresh_disbursement_status(client, disbursement_id=uuid.UUID(row["id"]))
        if outcome["status"] in ("PROCESSING", "NEEDS_RECONCILIATION"):
            still_pending += 1
        else:
            resolved += 1

    return {"checked": len(rows), "resolved": resolved, "still_pending": still_pending}


def reverse_successful_disbursement_from_callback(
    client: Client, *, provider_reference: str, reason: str | None
) -> dict | None:
    """Reverses an already-SUCCESS payout after Selcom reports it bounced
    after the fact (e.g. an invalid bank account only discovered once
    settlement was attempted) — credits the merchant's wallet back.

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
    amount = Decimal(str(existing.get("recipient_net_amount") or existing["amount"]))
    fee_amount = Decimal(str(existing.get("total_charges") or "0"))
    currency = existing["currency"]
    transaction = _find_transaction_for_disbursement(client, disbursement_id)
    transaction_id = uuid.UUID(transaction["id"])

    reverse_disbursement_entries(
        client,
        transaction_id=transaction_id,
        merchant_id=merchant_id,
        amount=amount,
        fee_amount=fee_amount,
        currency=currency,
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
        notification_type=NotificationType.WITHDRAWAL_REVERSED,
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
