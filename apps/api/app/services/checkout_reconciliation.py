"""Shared completion logic for Selcom Checkout wallet-push collections —
the one place both the inbound webhook handler
(app/routers/webhooks.py::selcom_checkout_webhook) and the manual
order-status refresh endpoints
(POST /v1/merchant/collections/{id}/refresh-status,
POST /v1/admin/collections/{id}/refresh-status) apply a Selcom result to
a collection.

**Reuses app/services/collections.py::resolve_collection() rather than
reimplementing crediting** — that function already does everything the
credit rule needs: idempotent (a no-op if the collection isn't still
"processing"), posts ledger entries exactly once, marks a linked
payment_link PAID and a linked invoice PAID/PARTIALLY_PAID, and enqueues
the outbound developer webhook event. This module's own job is just:
map Selcom Checkout's fields onto the CollectionResult shape
resolve_collection() already understands, and additionally keep
checkout_orders (a concept resolve_collection() has no reason to know
about) and the merchant notification in sync.

Credit rule (never decided anywhere else): a collection is only ever
resolved "successful" — and therefore only ever credited — when all
three of result == "SUCCESS", resultcode == "000", and
payment_status == "COMPLETED" agree. A payment_status of "COMPLETED"
without the other two agreeing is treated as still-unresolved
("processing"), not silently accepted and not silently marked
failed — that combination is corrupted/suspicious input, not a normal
outcome, and the safe response to "the signal doesn't add up" is to
leave money movement pending, never to guess.
"""

import uuid

from supabase import Client

from app.core.errors import ConflictError, NotFoundError
from app.schemas.enums import NotificationType
from app.services.collections import resolve_collection, reverse_successful_collection
from app.services.crud import execute_maybe_single, get_by_id, update_row
from app.services.notifications_service import notify_merchant
from app.services.selcom.schemas import CollectionResult, ProviderStatus
from app.services.selcom_checkout.client import (
    SelcomCheckoutHTTPClient,
    get_selcom_checkout_credentials,
)

_COMPLETED_PAYMENT_STATUSES = {"COMPLETED"}
# REVERSED is Selcom reporting that a payment it earlier called COMPLETED
# has since bounced (e.g. the live incident this module was hardened for:
# an M-Pesa "own till" payment that Selcom accepted then reversed) — a
# terminal failure/reversal outcome either way, never silently treated as
# still-pending.
_TERMINAL_FAILED_PAYMENT_STATUSES = {"CANCELLED", "USERCANCELLED", "REJECTED", "REVERSED"}
_STILL_PENDING_PAYMENT_STATUSES = {"PENDING", "INPROGRESS"}

# Selcom's free-text message/result fields have carried this wording on
# real deliveries (see the live incident's own M-Pesa message: "Payment
# unsuccessful. You are trying to pay into your own till") — checked as a
# belt-and-suspenders signal alongside payment_status, since a free-text
# field is far less reliable than a coded status but still worth catching
# when it's the only place the true outcome shows up.
_REVERSAL_MESSAGE_MARKERS = ("own till", "unsuccessful", "reversed", "reversal")


def _looks_like_reversal_message(raw_response: dict) -> str | None:
    message = str(raw_response.get("message") or "").strip()
    if not message:
        return None
    lowered = message.lower()
    if any(marker in lowered for marker in _REVERSAL_MESSAGE_MARKERS):
        return message
    return None


def map_checkout_status_to_provider_status(
    *, payment_status: str | None, result: str | None, resultcode: str | None
) -> ProviderStatus:
    """The credit rule, as a pure function so it's independently
    testable: result/resultcode/payment_status together decide
    "successful" / "processing" / "failed" — the same three-value
    vocabulary app/services/selcom/schemas.py::CollectionResult already
    uses, so the result plugs straight into resolve_collection()."""
    payment_status = (payment_status or "").upper()
    result = (result or "").upper()

    if payment_status in _COMPLETED_PAYMENT_STATUSES:
        if result == "SUCCESS" and resultcode == "000":
            return "successful"
        # COMPLETED without result/resultcode agreeing is inconsistent —
        # never credit on this alone, and don't mark it failed either
        # (that could hide a real success behind a mismatched field).
        # Stays "processing" — unresolved, safe, and still refreshable.
        return "processing"

    if payment_status in _TERMINAL_FAILED_PAYMENT_STATUSES:
        return "failed"

    if payment_status in _STILL_PENDING_PAYMENT_STATUSES:
        return "processing"

    # Unrecognized payment_status (or none at all — e.g. a bare
    # wallet-payment PENDING/111 result before any payment_status field
    # exists yet) — fall back to resultcode alone, same convention as
    # wallet-payment's own parsing.
    if resultcode == "000" and result == "SUCCESS":
        return "successful"
    if resultcode in ("111", "927"):
        return "processing"
    if resultcode == "999":
        return "processing"  # ambiguous — see module docstring, never a silent failure
    return "failed"


def find_collection_by_transid(client: Client, *, transid: str) -> dict | None:
    """The precise match for "which payment attempt is this delivery
    about" — transid is generated fresh per wallet-payment call
    (app/services/wallet_push.py), so unlike order_id (which can be
    reused across a retried order-creation-but-not-yet-pushed attempt)
    it identifies exactly one collection."""
    return execute_maybe_single(
        client.table("collections").select("*").eq("provider_transid", transid).maybe_single()
    )


def find_collection_by_order_id(client: Client, *, order_id: str) -> dict | None:
    """Fallback lookup when a delivery doesn't carry (or predates) a
    transid — resolves via the checkout_orders row's own order_id, then
    the collection linked to it."""
    order = execute_maybe_single(
        client.table("checkout_orders").select("id").eq("order_id", order_id).maybe_single()
    )
    if not order:
        return None
    return execute_maybe_single(
        client.table("collections")
        .select("*")
        .eq("checkout_order_id", order["id"])
        .order("created_at", desc=True)
        .range(0, 0)
        .maybe_single()
    )


async def complete_checkout_collection_once(
    client: Client,
    *,
    collection_id: uuid.UUID,
    payment_status: str | None,
    result: str | None,
    resultcode: str | None,
    reference: str | None,
    transid: str | None,
    channel: str | None,
    raw_response: dict,
) -> dict | None:
    """Applies one Selcom Checkout result to a collection, exactly once
    per resolution — safe to call repeatedly (a webhook retry, or a
    status refresh after the webhook already resolved it) without
    double-crediting, since resolve_collection() itself no-ops once the
    collection is no longer "processing". Audit fields (provider_*,
    channel, raw_response) are refreshed on every call regardless, so a
    later delivery's data is never lost even when it can't change the
    outcome anymore.

    A collection that's already "successful" and receives a *new* signal
    indicating the payment actually failed/reversed (payment_status ==
    REVERSED, or a terminal-failure payment_status, or Selcom's message
    text itself reads as a reversal — see module docstring/live incident)
    routes to reverse_successful_collection() instead of
    resolve_collection(), since resolve_collection()'s own idempotency
    guard would otherwise silently no-op on an already-resolved
    collection and the reversal would never be applied.

    Returns None if collection_id doesn't exist at all (caller decides
    whether that's a 404 or something to log and ACK anyway)."""
    collection = get_by_id(client, "collections", collection_id)
    if not collection:
        return None
    # Captured before resolve_collection() runs — its own idempotency
    # check is keyed on this same field, and this call needs to know
    # whether *this* call is the one doing the resolving, or a repeat
    # arriving after an earlier call already did. Skipping this check
    # would re-notify/re-mark the linked order "completed" on every
    # duplicate webhook delivery, even though the ledger itself stays
    # correctly protected by resolve_collection()'s own guard.
    was_still_processing = collection["status"] == "processing"
    was_already_successful = collection["status"] == "successful"

    update_row(
        client,
        "collections",
        collection_id,
        {
            "provider_reference": reference or collection.get("provider_reference"),
            "provider_transid": transid or collection.get("provider_transid"),
            "provider_result": result,
            "provider_resultcode": resultcode,
            "provider_payment_status": payment_status,
            "channel": channel or collection.get("channel"),
            "raw_response": raw_response,
        },
    )

    status = map_checkout_status_to_provider_status(
        payment_status=payment_status, result=result, resultcode=resultcode
    )
    reversal_message = _looks_like_reversal_message(raw_response)

    if was_already_successful and (status == "failed" or reversal_message):
        reason = (
            reversal_message
            or f"Selcom payment_status={payment_status or 'unknown'} after this collection had already settled"
        )
        return reverse_successful_collection(client, collection_id=collection_id, reason=reason)

    failure_reason = None
    if status == "failed":
        failure_reason = f"Selcom payment_status={payment_status or 'unknown'}"
    elif reversal_message:
        # payment_status/result/resultcode all looked fine, but the
        # free-text message itself reads as a reversal/failure — never
        # silently credited on a mixed signal like this (same "don't
        # guess" principle as the COMPLETED-without-agreement case
        # above), and also never left "processing" — it's treated as a
        # clear failure rather than an ambiguous one, since this text has
        # only ever meant "the money didn't actually move" so far.
        status = "failed"
        failure_reason = reversal_message

    collection_result = CollectionResult(
        provider="selcom_checkout",
        provider_reference=reference or collection.get("provider_reference") or "",
        status=status,
        failure_reason=failure_reason,
    )
    resolved = resolve_collection(client, collection_id=collection_id, result=collection_result)

    if was_still_processing and status == "successful" and resolved.get("status") == "successful":
        if collection.get("checkout_order_id"):
            update_row(client, "checkout_orders", uuid.UUID(collection["checkout_order_id"]), {"status": "completed"})
        notify_merchant(
            client,
            merchant_id=uuid.UUID(resolved["merchant_id"]),
            notification_type=NotificationType.PAYMENT_RECEIVED,
            title="Payment received",
            body=f"You received a payment of {resolved['amount']} {resolved['currency']}.",
            related_resource_type="collection",
            related_resource_id=collection_id,
        )

    return resolved


async def _query_and_complete_checkout_collection(client: Client, *, collection: dict, order_id: str) -> dict | None:
    """Shared core: queries Selcom's own order-status API with our own
    outbound-authenticated credentials, then applies *that* trustworthy
    answer via complete_checkout_collection_once(). Used by both the
    manual Refresh Status endpoints and (since 2026-08-27) the incoming
    webhook handler — see resolve_checkout_collection_from_webhook_hint's
    docstring for why the webhook never applies its own claimed fields
    directly."""
    checkout_client = SelcomCheckoutHTTPClient(credentials=get_selcom_checkout_credentials())
    status_result = await checkout_client.get_order_status(order_id=order_id)

    return await complete_checkout_collection_once(
        client,
        collection_id=uuid.UUID(collection["id"]),
        payment_status=status_result.payment_status,
        result=status_result.result,
        resultcode=status_result.resultcode,
        reference=status_result.reference,
        transid=status_result.transid or collection.get("provider_transid"),
        channel=status_result.channel,
        raw_response=status_result.raw_response,
    )


async def refresh_checkout_collection_status(client: Client, *, collection_id: uuid.UUID) -> dict:
    """The manual reconciliation path — queries Selcom directly
    (get_order_status()) rather than waiting for a webhook, and applies
    the same completion logic via complete_checkout_collection_once().
    This is a fully independent path from the webhook: it only ever
    calls Selcom, never receives from it."""
    collection = get_by_id(client, "collections", collection_id)
    if not collection:
        raise NotFoundError("Collection not found")
    if not collection.get("checkout_order_id"):
        raise ConflictError("This collection has no linked Selcom Checkout order to refresh")

    order = get_by_id(client, "checkout_orders", uuid.UUID(collection["checkout_order_id"]))
    if not order:
        raise ConflictError("The linked Selcom Checkout order no longer exists")

    resolved = await _query_and_complete_checkout_collection(client, collection=collection, order_id=order["order_id"])
    return resolved if resolved is not None else collection


async def resolve_checkout_collection_from_webhook_hint(
    client: Client, *, collection: dict, order_id: str
) -> dict | None:
    """Called by the webhook handler for every delivery it can match to a
    collection — regardless of what the delivery itself claims, and
    regardless of whether verify_webhook_signature accepted it.

    Confirmed against 5 independent real deliveries on 2026-08-27 (see
    app/services/selcom_checkout/signer.py::verify_webhook_signature's
    docstring): Selcom's real Checkout webhook callback carries no
    signature at all — no Digest/Timestamp/Digest-Method/Signed-Fields
    header, nothing else signature-shaped either. The inferred signing
    scheme that module was built against was simply wrong; it will
    reject every real delivery forever, not just a misconfigured one.

    Since there is no way to authenticate an inbound delivery, this never
    trusts one for something as consequential as crediting a payment —
    the delivery's own payment_status/result/resultcode are never applied
    directly. Instead it's treated purely as a "something may have
    changed, go check" signal: exactly like refresh_checkout_collection_status,
    it re-queries Selcom's order-status API with our own
    authenticated outbound credentials and applies only that answer. A
    forged or replayed webhook POST can therefore never credit a payment
    by itself — at worst it triggers one harmless status check that
    finds nothing new to apply."""
    return await _query_and_complete_checkout_collection(client, collection=collection, order_id=order_id)
