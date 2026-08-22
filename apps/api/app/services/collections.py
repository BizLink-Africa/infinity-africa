"""Collection lifecycle: create -> initiate with the provider -> resolve.

Every collection gets exactly one transaction row, created alongside it
(both PROCESSING) before the provider even confirms anything — reflecting
that money movement is "in flight" the moment a push/QR is issued, not
only once it's confirmed. resolve_collection() is the one place that ever
moves either of them out of "processing": it updates both in place (never
inserts a second transaction) and, on success, posts ledger entries and
applies the result to a linked payment_link/invoice.

Two ways a collection reaches resolve_collection():
  - execute_collection(): initiate, then immediately check_collection_status
    and resolve — synchronous, used by the public payment-link/invoice
    "collect" endpoints where the customer waits for a result.
  - resolve_collection_from_callback(): a provider's async callback (real,
    or a manual test) resolves a collection some time after
    initiate_collection()/initiate_dynamic_qr_collection() left it
    PROCESSING — used by /v1/collections/{method}, which returns PROCESSING
    immediately and never resolves synchronously.
"""

import uuid
from decimal import ROUND_HALF_UP, Decimal

from supabase import Client

from app.config import get_settings
from app.core.references import generate_reference
from app.core.time import utc_now_iso
from app.schemas.enums import CollectionMethod
from app.services.crud import execute_maybe_single, get_by_id, insert_row, update_row
from app.services.fraud_monitoring_service import evaluate_collection
from app.services.ledger import post_collection_entries
from app.services.selcom.client import get_selcom_client
from app.services.selcom.schemas import CollectionResult
from app.services.webhooks import enqueue_webhook_event


def _build_initiation_metadata(
    *,
    description: str | None,
    customer_name: str | None,
    customer_email: str | None,
    callback_url: str | None,
) -> dict:
    """collections has no dedicated columns for these — they ride along in
    metadata, same as description already did."""
    metadata = {}
    if description:
        metadata["description"] = description
    if customer_name:
        metadata["customer_name"] = customer_name
    if customer_email:
        metadata["customer_email"] = customer_email
    if callback_url:
        metadata["callback_url"] = callback_url
    return metadata


async def create_processing_collection(
    client: Client,
    *,
    merchant_id: uuid.UUID,
    method: CollectionMethod,
    amount: Decimal,
    currency: str,
    customer_id: uuid.UUID | None = None,
    customer_phone: str | None = None,
    customer_name: str | None = None,
    customer_email: str | None = None,
    payment_link_id: uuid.UUID | None = None,
    invoice_id: uuid.UUID | None = None,
    merchant_reference: str | None = None,
    description: str | None = None,
    callback_url: str | None = None,
) -> dict:
    """Inserts just the collection row (status='processing', no provider
    info yet). Split out from initiate_collection() so
    initiate_dynamic_qr_collection() can share it without going through
    the push-specific provider call."""
    return insert_row(
        client,
        "collections",
        {
            "merchant_id": str(merchant_id),
            "customer_id": str(customer_id) if customer_id else None,
            "payment_link_id": str(payment_link_id) if payment_link_id else None,
            "invoice_id": str(invoice_id) if invoice_id else None,
            "merchant_reference": merchant_reference,
            "method": method.value,
            "amount": str(amount),
            "currency": currency,
            "customer_phone": customer_phone,
            "status": "processing",
            "metadata": _build_initiation_metadata(
                description=description,
                customer_name=customer_name,
                customer_email=customer_email,
                callback_url=callback_url,
            ),
            "initiated_at": utc_now_iso(),
        },
    )


def create_processing_transaction(
    client: Client,
    *,
    merchant_id: uuid.UUID,
    method: str,
    collection_id: str,
    provider_reference: str,
    amount: Decimal,
    currency: str,
) -> dict:
    """Public (not `_`-prefixed) since app/services/wallet_push.py also
    needs it — every collection resolve_collection() might later resolve
    needs exactly one linked transaction row for ledger posting
    (gross/fee/net amounts), regardless of which client actually
    initiated it."""
    settings = get_settings()
    fee_amount = (amount * settings.platform_fee_percentage / Decimal(100)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    net_amount = amount - fee_amount

    return insert_row(
        client,
        "transactions",
        {
            "merchant_id": str(merchant_id),
            "reference": generate_reference("TXN"),
            "provider_reference": provider_reference,
            "type": "collection",
            "method": method,
            "collection_id": collection_id,
            "gross_amount": str(amount),
            "fee_amount": str(fee_amount),
            "net_amount": str(net_amount),
            "currency": currency,
            "status": "processing",
        },
    )


def _find_transaction_for_collection(client: Client, collection_id: uuid.UUID) -> dict | None:
    query = client.table("transactions").select("*").eq("collection_id", str(collection_id)).maybe_single()
    return execute_maybe_single(query)


_PUSH_INITIATION_MESSAGES: dict[str, str] = {
    "USSD_PUSH": "A USSD prompt was sent to the customer's phone — awaiting approval.",
    "STK_PUSH": "An STK push was sent to the customer's phone — awaiting approval.",
    "SELCOM_PESA_PUSH": "A payment request was sent to the customer's Selcom Pesa wallet — awaiting approval.",
}


async def initiate_collection(
    client: Client,
    *,
    merchant_id: uuid.UUID,
    method: CollectionMethod,
    amount: Decimal,
    currency: str,
    customer_id: uuid.UUID | None = None,
    customer_phone: str | None = None,
    customer_name: str | None = None,
    customer_email: str | None = None,
    payment_link_id: uuid.UUID | None = None,
    invoice_id: uuid.UUID | None = None,
    merchant_reference: str | None = None,
    description: str | None = None,
    callback_url: str | None = None,
) -> dict:
    """Creates the collection + its transaction and pushes it to the
    provider. Returns with status still PROCESSING — this is what
    /v1/collections/{method} uses directly, returning to the caller before
    anything is resolved. `transaction_reference` and `message` are added
    onto the returned dict (not collections table columns) so the router
    can build a response without a second lookup."""
    collection = await create_processing_collection(
        client,
        merchant_id=merchant_id,
        method=method,
        amount=amount,
        currency=currency,
        customer_id=customer_id,
        customer_phone=customer_phone,
        customer_name=customer_name,
        customer_email=customer_email,
        payment_link_id=payment_link_id,
        invoice_id=invoice_id,
        merchant_reference=merchant_reference,
        description=description,
        callback_url=callback_url,
    )

    provider = get_selcom_client()
    result = await provider.initiate_collection(
        method=method.value,
        amount=amount,
        currency=currency,
        customer_phone=customer_phone,
        reference=generate_reference("COL"),
    )

    collection = update_row(
        client,
        "collections",
        uuid.UUID(collection["id"]),
        {"provider": result.provider, "provider_reference": result.provider_reference},
    )

    transaction = create_processing_transaction(
        client,
        merchant_id=merchant_id,
        method=method.value,
        collection_id=collection["id"],
        provider_reference=result.provider_reference,
        amount=amount,
        currency=currency,
    )

    evaluate_collection(client, collection=collection, transaction=transaction, event="initiated")

    collection["transaction_reference"] = transaction["reference"]
    collection["message"] = _PUSH_INITIATION_MESSAGES.get(method.value)
    return collection


def resolve_collection(client: Client, *, collection_id: uuid.UUID, result: CollectionResult) -> dict:
    """Applies a final provider outcome to a PROCESSING collection: updates
    the collection + its transaction in place, posts ledger entries on
    success, applies the result to a linked payment_link/invoice, and
    enqueues a webhook event. A no-op (returns the row as-is) if the
    collection doesn't exist or was already resolved — callers may retry
    resolution without double-applying it."""
    collection = get_by_id(client, "collections", collection_id)
    if not collection or collection["status"] != "processing":
        return collection

    if result.status == "processing":
        # Not yet resolved by the provider (e.g. a real push the customer
        # hasn't approved yet) — leave the collection/transaction PROCESSING.
        # Final resolution comes from a later check_collection_status call
        # or the /v1/webhooks/selcom callback, both of which route back
        # through this same function.
        return collection

    merchant_id = uuid.UUID(collection["merchant_id"])
    currency = collection["currency"]
    final_status = "successful" if result.status == "successful" else "failed"

    collection_update = {"status": final_status, "completed_at": utc_now_iso()}
    if final_status == "failed":
        collection_update["failure_reason"] = result.failure_reason
    collection = update_row(client, "collections", collection_id, collection_update)

    transaction = _find_transaction_for_collection(client, collection_id)

    if final_status == "successful":
        update_row(client, "transactions", uuid.UUID(transaction["id"]), {"status": "successful"})
        post_collection_entries(
            client,
            transaction_id=uuid.UUID(transaction["id"]),
            merchant_id=merchant_id,
            gross_amount=Decimal(str(transaction["gross_amount"])),
            fee_amount=Decimal(str(transaction["fee_amount"])),
            net_amount=Decimal(str(transaction["net_amount"])),
            currency=currency,
        )
        _apply_collection_success(client, collection)
        evaluate_collection(client, collection=collection, transaction=transaction, event="resolved")
        enqueue_webhook_event(
            client,
            merchant_id=merchant_id,
            event_name="collection.success",
            payload={"collection_id": str(collection_id), "amount": collection["amount"], "currency": currency},
        )
    else:
        update_row(client, "transactions", uuid.UUID(transaction["id"]), {"status": "failed"})
        enqueue_webhook_event(
            client,
            merchant_id=merchant_id,
            event_name="collection.failed",
            payload={"collection_id": str(collection_id), "reason": result.failure_reason},
        )

    return collection


def _apply_collection_success(client: Client, collection: dict) -> None:
    if collection.get("payment_link_id"):
        payment_link_id = uuid.UUID(collection["payment_link_id"])
        update_row(client, "payment_links", payment_link_id, {"status": "PAID", "paid_at": utc_now_iso()})
        enqueue_webhook_event(
            client,
            merchant_id=uuid.UUID(collection["merchant_id"]),
            event_name="payment_link.paid",
            payload={"payment_link_id": str(payment_link_id), "collection_id": collection["id"]},
        )

        # An invoice's "Pay Now" link is a payment_links row the invoice
        # references (invoices.payment_link_id) — the collection itself only
        # ever knows about the payment_link, not the invoice, so the link
        # back to the invoice (if any) has to be looked up here.
        linked_invoice = execute_maybe_single(
            client.table("invoices").select("id").eq("payment_link_id", str(payment_link_id)).maybe_single()
        )
        if linked_invoice:
            _apply_payment_to_invoice(
                client,
                invoice_id=uuid.UUID(linked_invoice["id"]),
                amount=Decimal(str(collection["amount"])),
            )

    if collection.get("invoice_id"):
        _apply_payment_to_invoice(
            client, invoice_id=uuid.UUID(collection["invoice_id"]), amount=Decimal(str(collection["amount"]))
        )


def _apply_payment_to_invoice(client: Client, *, invoice_id: uuid.UUID, amount: Decimal) -> None:
    invoice = get_by_id(client, "invoices", invoice_id)
    if not invoice:
        return

    new_amount_paid = Decimal(str(invoice["amount_paid"])) + amount
    total_amount = Decimal(str(invoice["total_amount"]))
    new_status = "PAID" if new_amount_paid >= total_amount else "PARTIALLY_PAID"

    update_row(client, "invoices", invoice_id, {"amount_paid": str(new_amount_paid), "status": new_status})

    if new_status == "PAID":
        enqueue_webhook_event(
            client,
            merchant_id=uuid.UUID(invoice["merchant_id"]),
            event_name="invoice.paid",
            payload={"invoice_id": str(invoice_id)},
        )


async def execute_collection(
    client: Client,
    *,
    merchant_id: uuid.UUID,
    method: CollectionMethod,
    amount: Decimal,
    currency: str,
    customer_id: uuid.UUID | None = None,
    customer_phone: str | None = None,
    payment_link_id: uuid.UUID | None = None,
    invoice_id: uuid.UUID | None = None,
    description: str | None = None,
) -> dict:
    """Synchronous collection: initiate, then immediately check status and
    resolve. Used by the public payment-link/invoice "collect" endpoints,
    where the customer is waiting on the checkout page for a final result."""
    collection = await initiate_collection(
        client,
        merchant_id=merchant_id,
        method=method,
        amount=amount,
        currency=currency,
        customer_id=customer_id,
        customer_phone=customer_phone,
        payment_link_id=payment_link_id,
        invoice_id=invoice_id,
        description=description,
    )

    provider = get_selcom_client()
    result = await provider.check_collection_status(provider_reference=collection["provider_reference"])

    return resolve_collection(client, collection_id=uuid.UUID(collection["id"]), result=result)


async def initiate_dynamic_qr_collection(
    client: Client,
    *,
    merchant_id: uuid.UUID,
    amount: Decimal,
    currency: str,
    customer_id: uuid.UUID | None = None,
    customer_phone: str | None = None,
    customer_name: str | None = None,
    customer_email: str | None = None,
    payment_link_id: uuid.UUID | None = None,
    invoice_id: uuid.UUID | None = None,
    merchant_reference: str | None = None,
    description: str | None = None,
    callback_url: str | None = None,
):
    """Same shape as initiate_collection(), but generates a QR payload
    instead of pushing to a phone. Returns (collection, DynamicQrResult) —
    the QR payload/expiry aren't collection-table columns, so the caller
    needs both to build its response."""
    collection = await create_processing_collection(
        client,
        merchant_id=merchant_id,
        method=CollectionMethod.DYNAMIC_QR,
        amount=amount,
        currency=currency,
        customer_id=customer_id,
        customer_phone=customer_phone,
        customer_name=customer_name,
        customer_email=customer_email,
        payment_link_id=payment_link_id,
        invoice_id=invoice_id,
        merchant_reference=merchant_reference,
        description=description,
        callback_url=callback_url,
    )

    provider = get_selcom_client()
    qr_result = await provider.generate_dynamic_qr(
        amount=amount, currency=currency, reference=generate_reference("COL")
    )

    metadata = dict(collection.get("metadata") or {})
    metadata["qr_payload"] = qr_result.qr_payload
    metadata["qr_expires_at"] = qr_result.qr_expires_at.isoformat()

    collection = update_row(
        client,
        "collections",
        uuid.UUID(collection["id"]),
        {
            "provider": qr_result.provider,
            "provider_reference": qr_result.provider_reference,
            "metadata": metadata,
        },
    )

    transaction = create_processing_transaction(
        client,
        merchant_id=merchant_id,
        method=CollectionMethod.DYNAMIC_QR.value,
        collection_id=collection["id"],
        provider_reference=qr_result.provider_reference,
        amount=amount,
        currency=currency,
    )

    evaluate_collection(client, collection=collection, transaction=transaction, event="initiated")

    collection["transaction_reference"] = transaction["reference"]
    collection["message"] = "Scan the QR code with a mobile money app to complete payment."
    return collection, qr_result


async def execute_dynamic_qr_collection(
    client: Client,
    *,
    merchant_id: uuid.UUID,
    amount: Decimal,
    currency: str,
    customer_id: uuid.UUID | None = None,
    customer_phone: str | None = None,
    payment_link_id: uuid.UUID | None = None,
    invoice_id: uuid.UUID | None = None,
    description: str | None = None,
):
    """The DYNAMIC_QR counterpart to execute_collection() — used by the
    public payment-link/invoice "collect" endpoints. Unlike a push, there's
    nothing to synchronously check yet: the QR has to exist before anyone
    can scan it. Returns (collection, DynamicQrResult) still PROCESSING;
    resolution comes later from the /v1/webhooks/selcom callback via
    resolve_collection_from_callback()."""
    return await initiate_dynamic_qr_collection(
        client,
        merchant_id=merchant_id,
        amount=amount,
        currency=currency,
        customer_id=customer_id,
        customer_phone=customer_phone,
        payment_link_id=payment_link_id,
        invoice_id=invoice_id,
        description=description,
    )


def resolve_collection_from_callback(
    client: Client,
    *,
    provider_reference: str,
    status: str,
    failure_reason: str | None,
) -> dict | None:
    """Resolves a collection left PROCESSING by an asynchronous provider
    callback — what /v1/collections/{method} initiates and never resolves
    itself, and what a real Selcom callback would land on."""
    existing = execute_maybe_single(
        client.table("collections")
        .select("*")
        .eq("provider_reference", provider_reference)
        .eq("status", "processing")
        .maybe_single()
    )
    if not existing:
        return None

    result = CollectionResult(
        provider=existing.get("provider") or "mock_selcom",
        provider_reference=provider_reference,
        status="successful" if status == "successful" else "failed",
        failure_reason=failure_reason,
    )
    return resolve_collection(client, collection_id=uuid.UUID(existing["id"]), result=result)
