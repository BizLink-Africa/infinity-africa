"""Self-service Merchant Portal API — /v1/merchant/*.

Every endpoint here resolves the caller's merchant purely from their JWT
(app.auth.get_own_merchant / require_own_merchant_role) — unlike every
other router, the client never supplies a merchant_id at all, in the path,
query, or body. Everything below delegates to the same services the
existing /v1/payment-links, /v1/invoices, /v1/collections/{method},
/v1/disbursements/{method}, /v1/merchants/{id}/transactions, and
/v1/merchants/{id}/api-keys routers already use — no business logic is
reimplemented here, only re-exposed at merchant-scoped-by-JWT paths.

"Withdrawals" here is the same thing as "disbursements" everywhere else in
the codebase (schema, table, services) — user-facing naming only, matching
the Merchant Portal frontend's existing "Withdraw"/"Withdrawals" copy. The
existing /v1/disbursements/* routes are untouched.
"""

import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile, status

from app.auth import hash_api_key, require_own_merchant_role
from app.core.errors import ConflictError, NotFoundError, ValidationAPIError
from app.core.pagination import PaginationParams, build_page_meta, pagination_params
from app.core.references import generate_reference
from app.database.session import get_supabase_admin
from app.schemas.api_keys import ApiKeyCreate, ApiKeyCreateResponse, ApiKeyResponse
from app.schemas.auth import MerchantMembership
from app.schemas.collections import CollectionResponse, DynamicQrCollectionResponse
from app.schemas.common import APIResponse
from app.schemas.disbursements import DisbursementResponse
from app.schemas.disputes import (
    DisputeMessageCreate,
    DisputeResponse,
    RequestRefundInput,
)
from app.schemas.document_requests import DocumentRequestResponse
from app.schemas.enums import CollectionMethod, UserRole
from app.schemas.fraud import FraudAlertResponse
from app.schemas.invoices import InvoiceItemResponse, InvoiceResponse, InvoiceUpdate
from app.schemas.merchant_portal import (
    MerchantDynamicQrCollectionRequest,
    MerchantInvoiceCreate,
    MerchantOverviewResponse,
    MerchantPaymentLinkCreate,
    MerchantPaymentLinkUpdate,
    MerchantPushCollectionRequest,
    WithdrawalCreate,
)
from app.schemas.merchants import MerchantResponse
from app.schemas.notifications import NotificationResponse
from app.schemas.payment_links import PaymentLinkResponse
from app.schemas.refunds import RefundResponse
from app.schemas.transactions import TransactionResponse
from app.schemas.withdrawals import FeeBreakdown, WithdrawalQuoteRequest
from app.services import disputes_service, document_requests_service
from app.services.audit import write_audit_log
from app.services.collections import initiate_collection, initiate_dynamic_qr_collection
from app.services.crud import (
    execute_maybe_single,
    get_by_id,
    insert_row,
    list_for_merchant,
    update_row,
)
from app.services.disbursements import execute_disbursement, quote_withdrawal_fee
from app.services.idempotency import run_idempotent
from app.services.merchant_overview import get_merchant_overview
from app.services.payment_links import (
    batch_collection_counts,
    build_public_url,
    generate_public_slug,
    validate_payment_link_for_collection,
    with_effective_status,
)

router = APIRouter(prefix="/merchant", tags=["merchant-portal"])

_ADMIN_AND_STAFF = (UserRole.MERCHANT_ADMIN, UserRole.MERCHANT_STAFF)
_ADMIN_ONLY = (UserRole.MERCHANT_ADMIN,)
_ADMIN_AND_DEVELOPER = (UserRole.MERCHANT_ADMIN, UserRole.DEVELOPER)


# --- Profile / overview ------------------------------------------------------


@router.get("/me", response_model=APIResponse[MerchantResponse])
def get_my_merchant(
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role())],
):
    client = get_supabase_admin()
    row = get_by_id(client, "merchants", membership.merchant_id)
    if not row:
        raise NotFoundError("Merchant not found")
    return APIResponse(data=MerchantResponse(**row))


@router.get("/overview", response_model=APIResponse[MerchantOverviewResponse])
def get_my_overview(
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role())],
):
    client = get_supabase_admin()
    overview = get_merchant_overview(client, merchant_id=membership.merchant_id)
    return APIResponse(data=MerchantOverviewResponse(**overview))


# --- Payment links ------------------------------------------------------------


def _payment_link_response(row: dict, *, attempt_count: int = 0) -> PaymentLinkResponse:
    return PaymentLinkResponse(
        **row, public_url=build_public_url(row["public_slug"]), attempt_count=attempt_count
    )


@router.get("/payment-links", response_model=APIResponse[list[PaymentLinkResponse]])
def list_my_payment_links(
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
):
    client = get_supabase_admin()
    rows, total = list_for_merchant(client, "payment_links", merchant_id=membership.merchant_id, pagination=pagination)
    rows = [with_effective_status(client, row) for row in rows]
    counts = batch_collection_counts(client, {row["id"] for row in rows})
    data = [_payment_link_response(row, attempt_count=counts.get(row["id"], 0)) for row in rows]
    return APIResponse(data=data, meta=build_page_meta(pagination, total))


@router.post("/payment-links", response_model=APIResponse[PaymentLinkResponse], status_code=status.HTTP_201_CREATED)
async def create_my_payment_link(
    payload: MerchantPaymentLinkCreate,
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
):
    client = get_supabase_admin()

    async def _handler() -> tuple[int, dict]:
        data = payload.model_dump(mode="json", exclude={"allowed_payment_methods"})
        data["merchant_id"] = str(membership.merchant_id)
        data["allowed_payment_methods"] = [m.value for m in payload.allowed_payment_methods]
        data["public_slug"] = generate_public_slug()
        data["status"] = "ACTIVE"

        row = insert_row(client, "payment_links", data)

        write_audit_log(
            client,
            actor_id=membership.user_id,
            actor_type="user",
            merchant_id=membership.merchant_id,
            action="payment_link.created",
            resource_type="payment_link",
            resource_id=uuid.UUID(row["id"]),
        )
        return status.HTTP_201_CREATED, row

    _status_code, body = await run_idempotent(
        client,
        merchant_id=membership.merchant_id,
        endpoint="POST /v1/merchant/payment-links",
        idempotency_key=idempotency_key,
        request_payload=payload.model_dump(mode="json"),
        handler=_handler,
    )
    return APIResponse(data=_payment_link_response(body))


@router.get("/payment-links/{link_id}", response_model=APIResponse[PaymentLinkResponse])
def get_my_payment_link(
    link_id: uuid.UUID,
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
):
    client = get_supabase_admin()
    row = get_by_id(client, "payment_links", link_id)
    if not row or uuid.UUID(row["merchant_id"]) != membership.merchant_id:
        raise NotFoundError("Payment link not found")
    row = with_effective_status(client, row)
    counts = batch_collection_counts(client, {row["id"]})
    return APIResponse(data=_payment_link_response(row, attempt_count=counts.get(row["id"], 0)))


@router.patch("/payment-links/{link_id}", response_model=APIResponse[PaymentLinkResponse])
def update_my_payment_link(
    link_id: uuid.UUID,
    payload: MerchantPaymentLinkUpdate,
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
):
    """Only an ACTIVE link may be edited — a PAID/EXPIRED/CANCELLED link's
    terms shouldn't change after the fact (a customer may have already seen
    the old terms, or already paid under them)."""
    client = get_supabase_admin()
    row = get_by_id(client, "payment_links", link_id)
    if not row or uuid.UUID(row["merchant_id"]) != membership.merchant_id:
        raise NotFoundError("Payment link not found")

    row = with_effective_status(client, row)
    if row["status"] != "ACTIVE":
        raise ConflictError(f"Only an ACTIVE payment link can be edited (status: {row['status']})")

    update_data = payload.model_dump(mode="json", exclude_unset=True, exclude={"allowed_payment_methods"})
    if payload.allowed_payment_methods is not None:
        update_data["allowed_payment_methods"] = [m.value for m in payload.allowed_payment_methods]

    if update_data:
        row = update_row(client, "payment_links", link_id, update_data) or row
        write_audit_log(
            client,
            actor_id=membership.user_id,
            actor_type="user",
            merchant_id=membership.merchant_id,
            action="payment_link.updated",
            resource_type="payment_link",
            resource_id=link_id,
            metadata={"fields": sorted(update_data.keys())},
        )

    counts = batch_collection_counts(client, {row["id"]})
    return APIResponse(data=_payment_link_response(row, attempt_count=counts.get(row["id"], 0)))


@router.patch("/payment-links/{link_id}/cancel", response_model=APIResponse[PaymentLinkResponse])
def cancel_my_payment_link(
    link_id: uuid.UUID,
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
):
    client = get_supabase_admin()
    row = get_by_id(client, "payment_links", link_id)
    if not row or uuid.UUID(row["merchant_id"]) != membership.merchant_id:
        raise NotFoundError("Payment link not found")

    row = with_effective_status(client, row)
    if row["status"] == "PAID":
        raise ConflictError("A paid payment link cannot be cancelled")

    if row["status"] != "CANCELLED":
        row = update_row(client, "payment_links", link_id, {"status": "CANCELLED"}) or row
        write_audit_log(
            client,
            actor_id=membership.user_id,
            actor_type="user",
            merchant_id=membership.merchant_id,
            action="payment_link.cancelled",
            resource_type="payment_link",
            resource_id=link_id,
        )
    return APIResponse(data=_payment_link_response(row))


# --- Invoices -----------------------------------------------------------------


def _fetch_invoice_items(client, invoice_id: uuid.UUID) -> list[dict]:
    result = client.table("invoice_items").select("*").eq("invoice_id", str(invoice_id)).order("sort_order").execute()
    return result.data or []


def _invoice_response(client, row: dict) -> InvoiceResponse:
    items = _fetch_invoice_items(client, uuid.UUID(row["id"]))
    return InvoiceResponse(**row, items=[InvoiceItemResponse(**item) for item in items])


@router.get("/invoices", response_model=APIResponse[list[InvoiceResponse]])
def list_my_invoices(
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
):
    client = get_supabase_admin()
    rows, total = list_for_merchant(client, "invoices", merchant_id=membership.merchant_id, pagination=pagination)
    data = [_invoice_response(client, row) for row in rows]
    return APIResponse(data=data, meta=build_page_meta(pagination, total))


@router.post("/invoices", response_model=APIResponse[InvoiceResponse], status_code=status.HTTP_201_CREATED)
def create_my_invoice(
    payload: MerchantInvoiceCreate,
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
):
    client = get_supabase_admin()

    subtotal = sum((item.quantity * item.unit_price for item in payload.items), Decimal(0))
    total_amount = subtotal + payload.tax_amount - payload.discount_amount
    if total_amount < 0:
        raise ValidationAPIError("Total amount cannot be negative")

    invoice_data = payload.model_dump(mode="json", exclude={"items"})
    invoice_data["merchant_id"] = str(membership.merchant_id)
    invoice_data["invoice_number"] = generate_reference("INV")
    invoice_data["subtotal"] = str(subtotal)
    invoice_data["total_amount"] = str(total_amount)
    invoice_data["amount_paid"] = "0"
    invoice_data["status"] = "DRAFT"

    invoice = insert_row(client, "invoices", invoice_data)
    invoice_id = invoice["id"]

    items_data = [{**item.model_dump(mode="json"), "invoice_id": invoice_id} for item in payload.items]
    client.table("invoice_items").insert(items_data).execute()

    write_audit_log(
        client,
        actor_id=membership.user_id,
        actor_type="user",
        merchant_id=membership.merchant_id,
        action="invoice.created",
        resource_type="invoice",
        resource_id=uuid.UUID(invoice_id),
    )
    return APIResponse(data=_invoice_response(client, invoice))


@router.get("/invoices/{invoice_id}", response_model=APIResponse[InvoiceResponse])
def get_my_invoice(
    invoice_id: uuid.UUID,
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
):
    client = get_supabase_admin()
    row = get_by_id(client, "invoices", invoice_id)
    if not row or uuid.UUID(row["merchant_id"]) != membership.merchant_id:
        raise NotFoundError("Invoice not found")
    return APIResponse(data=_invoice_response(client, row))


@router.patch("/invoices/{invoice_id}", response_model=APIResponse[InvoiceResponse])
def update_my_invoice(
    invoice_id: uuid.UUID,
    payload: InvoiceUpdate,
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
):
    client = get_supabase_admin()
    row = get_by_id(client, "invoices", invoice_id)
    if not row or uuid.UUID(row["merchant_id"]) != membership.merchant_id:
        raise NotFoundError("Invoice not found")

    if row["status"] != "DRAFT":
        raise ValidationAPIError("Only a draft invoice can be edited")

    update_data = payload.model_dump(mode="json", exclude={"items"}, exclude_unset=True)

    if payload.items is not None:
        subtotal = sum((item.quantity * item.unit_price for item in payload.items), Decimal(0))
        tax_amount = payload.tax_amount if payload.tax_amount is not None else Decimal(str(row["tax_amount"]))
        discount_amount = (
            payload.discount_amount if payload.discount_amount is not None else Decimal(str(row["discount_amount"]))
        )
        total_amount = subtotal + tax_amount - discount_amount
        if total_amount < 0:
            raise ValidationAPIError("Total amount cannot be negative")

        update_data["subtotal"] = str(subtotal)
        update_data["total_amount"] = str(total_amount)

        client.table("invoice_items").delete().eq("invoice_id", str(invoice_id)).execute()
        items_data = [{**item.model_dump(mode="json"), "invoice_id": str(invoice_id)} for item in payload.items]
        client.table("invoice_items").insert(items_data).execute()
    elif payload.tax_amount is not None or payload.discount_amount is not None:
        subtotal = Decimal(str(row["subtotal"]))
        tax_amount = payload.tax_amount if payload.tax_amount is not None else Decimal(str(row["tax_amount"]))
        discount_amount = (
            payload.discount_amount if payload.discount_amount is not None else Decimal(str(row["discount_amount"]))
        )
        total_amount = subtotal + tax_amount - discount_amount
        if total_amount < 0:
            raise ValidationAPIError("Total amount cannot be negative")
        update_data["total_amount"] = str(total_amount)

    row = update_row(client, "invoices", invoice_id, update_data) or row
    write_audit_log(
        client,
        actor_id=membership.user_id,
        actor_type="user",
        merchant_id=membership.merchant_id,
        action="invoice.updated",
        resource_type="invoice",
        resource_id=invoice_id,
    )
    return APIResponse(data=_invoice_response(client, row))


@router.post("/invoices/{invoice_id}/send", response_model=APIResponse[InvoiceResponse])
def send_my_invoice(
    invoice_id: uuid.UUID,
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
):
    """DRAFT -> SENT. Not in the originally requested endpoint list, but
    needed for the Merchant Portal's existing "send now vs. save as draft"
    invoice-creation flow to actually work — mirrors the existing
    POST /v1/invoices/{id}/send exactly."""
    client = get_supabase_admin()
    row = get_by_id(client, "invoices", invoice_id)
    if not row or uuid.UUID(row["merchant_id"]) != membership.merchant_id:
        raise NotFoundError("Invoice not found")

    if row["status"] != "DRAFT":
        raise ValidationAPIError("Only a draft invoice can be sent")

    row = update_row(client, "invoices", invoice_id, {"status": "SENT"}) or row
    write_audit_log(
        client,
        actor_id=membership.user_id,
        actor_type="user",
        merchant_id=membership.merchant_id,
        action="invoice.sent",
        resource_type="invoice",
        resource_id=invoice_id,
    )
    return APIResponse(data=_invoice_response(client, row))


@router.post("/invoices/{invoice_id}/payment-link", response_model=APIResponse[PaymentLinkResponse])
def generate_my_invoice_payment_link(
    invoice_id: uuid.UUID,
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
):
    client = get_supabase_admin()
    row = get_by_id(client, "invoices", invoice_id)
    if not row or uuid.UUID(row["merchant_id"]) != membership.merchant_id:
        raise NotFoundError("Invoice not found")

    if row["status"] not in ("SENT", "PARTIALLY_PAID", "OVERDUE"):
        raise ValidationAPIError(
            f"Cannot generate a payment link for an invoice with status {row['status']}; send it first"
        )

    amount_due = Decimal(str(row["total_amount"])) - Decimal(str(row["amount_paid"]))
    if amount_due <= 0:
        raise ValidationAPIError("This invoice has no remaining balance")

    if row.get("payment_link_id"):
        existing = get_by_id(client, "payment_links", uuid.UUID(row["payment_link_id"]))
        existing = with_effective_status(client, existing) if existing else None
        if existing and existing["status"] == "ACTIVE":
            return APIResponse(data=_payment_link_response(existing))

    link_data = {
        "merchant_id": str(membership.merchant_id),
        "customer_id": row.get("customer_id"),
        "amount": str(amount_due),
        "currency": row["currency"],
        "customer_name": row.get("customer_name"),
        "customer_phone": row.get("customer_phone"),
        "description": f"Payment for invoice {row['invoice_number']}",
        "allowed_payment_methods": [m.value for m in CollectionMethod],
        "public_slug": generate_public_slug(),
        "status": "ACTIVE",
    }
    link = insert_row(client, "payment_links", link_data)
    update_row(client, "invoices", invoice_id, {"payment_link_id": link["id"]})

    write_audit_log(
        client,
        actor_id=membership.user_id,
        actor_type="user",
        merchant_id=membership.merchant_id,
        action="invoice.payment_link_generated",
        resource_type="invoice",
        resource_id=invoice_id,
        metadata={"payment_link_id": link["id"]},
    )
    return APIResponse(data=_payment_link_response(link))


# --- Collections ----------------------------------------------------------


_METHOD_PATHS: dict[CollectionMethod, str] = {
    CollectionMethod.USSD_PUSH: "ussd-push",
    CollectionMethod.STK_PUSH: "stk-push",
    CollectionMethod.SELCOM_PESA_PUSH: "selcom-pesa-push",
    CollectionMethod.DYNAMIC_QR: "dynamic-qr",
}


@router.get("/collections", response_model=APIResponse[list[CollectionResponse]])
def list_my_collections(
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
):
    client = get_supabase_admin()
    rows, total = list_for_merchant(client, "collections", merchant_id=membership.merchant_id, pagination=pagination)
    data = [CollectionResponse(**row) for row in rows]
    return APIResponse(data=data, meta=build_page_meta(pagination, total))


async def _create_my_push_collection(
    method: CollectionMethod,
    payload: MerchantPushCollectionRequest,
    membership: MerchantMembership,
    idempotency_key: str,
) -> APIResponse[CollectionResponse]:
    client = get_supabase_admin()

    await validate_payment_link_for_collection(
        client, merchant_id=membership.merchant_id, payment_link_id=payload.payment_link_id, method=method
    )

    async def _handler() -> tuple[int, dict]:
        collection = await initiate_collection(
            client,
            merchant_id=membership.merchant_id,
            method=method,
            amount=payload.amount,
            currency=payload.currency,
            customer_id=payload.customer_id,
            customer_phone=payload.customer_phone,
            customer_name=payload.customer_name,
            customer_email=payload.customer_email,
            payment_link_id=payload.payment_link_id,
            invoice_id=payload.invoice_id,
            merchant_reference=payload.merchant_reference,
            description=payload.description,
            callback_url=payload.callback_url,
        )
        write_audit_log(
            client,
            actor_id=membership.user_id,
            actor_type="user",
            merchant_id=membership.merchant_id,
            action="collection.initiated",
            resource_type="collection",
            resource_id=uuid.UUID(collection["id"]),
            metadata={"method": method.value},
        )
        return status.HTTP_202_ACCEPTED, collection

    _status_code, body = await run_idempotent(
        client,
        merchant_id=membership.merchant_id,
        endpoint=f"POST /v1/merchant/collections/{_METHOD_PATHS[method]}",
        idempotency_key=idempotency_key,
        request_payload=payload.model_dump(mode="json"),
        handler=_handler,
    )
    return APIResponse(data=CollectionResponse(**body))


@router.post(
    "/collections/ussd-push", response_model=APIResponse[CollectionResponse], status_code=status.HTTP_202_ACCEPTED
)
async def create_my_ussd_push_collection(
    payload: MerchantPushCollectionRequest,
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
):
    return await _create_my_push_collection(CollectionMethod.USSD_PUSH, payload, membership, idempotency_key)


@router.post(
    "/collections/stk-push", response_model=APIResponse[CollectionResponse], status_code=status.HTTP_202_ACCEPTED
)
async def create_my_stk_push_collection(
    payload: MerchantPushCollectionRequest,
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
):
    return await _create_my_push_collection(CollectionMethod.STK_PUSH, payload, membership, idempotency_key)


@router.post(
    "/collections/selcom-pesa-push",
    response_model=APIResponse[CollectionResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_my_selcom_pesa_push_collection(
    payload: MerchantPushCollectionRequest,
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
):
    return await _create_my_push_collection(CollectionMethod.SELCOM_PESA_PUSH, payload, membership, idempotency_key)


@router.post(
    "/collections/dynamic-qr",
    response_model=APIResponse[DynamicQrCollectionResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_my_dynamic_qr_collection(
    payload: MerchantDynamicQrCollectionRequest,
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
):
    client = get_supabase_admin()

    await validate_payment_link_for_collection(
        client,
        merchant_id=membership.merchant_id,
        payment_link_id=payload.payment_link_id,
        method=CollectionMethod.DYNAMIC_QR,
    )

    async def _handler() -> tuple[int, dict]:
        collection, qr_result = await initiate_dynamic_qr_collection(
            client,
            merchant_id=membership.merchant_id,
            amount=payload.amount,
            currency=payload.currency,
            customer_id=payload.customer_id,
            customer_phone=payload.customer_phone,
            customer_name=payload.customer_name,
            customer_email=payload.customer_email,
            payment_link_id=payload.payment_link_id,
            invoice_id=payload.invoice_id,
            merchant_reference=payload.merchant_reference,
            description=payload.description,
            callback_url=payload.callback_url,
        )
        write_audit_log(
            client,
            actor_id=membership.user_id,
            actor_type="user",
            merchant_id=membership.merchant_id,
            action="collection.initiated",
            resource_type="collection",
            resource_id=uuid.UUID(collection["id"]),
            metadata={"method": "DYNAMIC_QR"},
        )
        body = {
            **collection,
            "qr_payload": qr_result.qr_payload,
            "qr_expires_at": qr_result.qr_expires_at.isoformat(),
            "expires_at": qr_result.qr_expires_at.isoformat(),
        }
        return status.HTTP_202_ACCEPTED, body

    _status_code, body = await run_idempotent(
        client,
        merchant_id=membership.merchant_id,
        endpoint="POST /v1/merchant/collections/dynamic-qr",
        idempotency_key=idempotency_key,
        request_payload=payload.model_dump(mode="json"),
        handler=_handler,
    )
    return APIResponse(data=DynamicQrCollectionResponse(**body))


# --- Withdrawals (disbursements) --------------------------------------------


@router.post("/withdrawals/quote", response_model=APIResponse[FeeBreakdown])
def quote_my_withdrawal(
    payload: WithdrawalQuoteRequest,
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
):
    """Read-only fee calculation — no withdrawal is created, no funds are
    reserved, Selcom is never called. Lets the merchant see the full charge
    breakdown before submitting (POST /withdrawals below), which
    recalculates and freezes the same breakdown server-side rather than
    trusting whatever this call returned."""
    client = get_supabase_admin()
    breakdown = quote_withdrawal_fee(
        client,
        merchant_id=membership.merchant_id,
        amount=payload.amount,
        method=payload.method,
        destination_code=payload.destination_code,
    )
    return APIResponse(data=breakdown)


@router.get("/withdrawals", response_model=APIResponse[list[DisbursementResponse]])
def list_my_withdrawals(
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
):
    client = get_supabase_admin()
    rows, total = list_for_merchant(client, "disbursements", merchant_id=membership.merchant_id, pagination=pagination)
    data = [DisbursementResponse(**row) for row in rows]
    return APIResponse(data=data, meta=build_page_meta(pagination, total))


@router.post("/withdrawals", response_model=APIResponse[DisbursementResponse], status_code=status.HTTP_202_ACCEPTED)
async def create_my_withdrawal(
    payload: WithdrawalCreate,
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_ONLY))],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
):
    """Merchant-admin only — a deliberate tightening vs. the existing
    /v1/disbursements/{method} routes, which also allow MERCHANT_STAFF.

    Always creates PENDING_ADMIN_APPROVAL, fee recalculated and frozen
    server-side (never trusts a client-supplied fee) — Selcom is never
    called from this path; only a Super Admin's approval
    (app/routers/admin_withdrawals.py) ever reaches the provider."""
    client = get_supabase_admin()

    async def _handler() -> tuple[int, dict]:
        disbursement = await execute_disbursement(
            client,
            merchant_id=membership.merchant_id,
            method=payload.method,
            amount=payload.amount,
            currency=payload.currency,
            destination_name=payload.resolved_destination_name,
            destination_identifier=payload.destination_identifier,
            destination_code=payload.destination_code,
            bank_name=payload.bank_name if payload.method.value == "BANK_ACCOUNT" else None,
            network=payload.network if payload.method.value == "MOBILE_MONEY" else None,
            description=payload.description,
        )
        write_audit_log(
            client,
            actor_id=membership.user_id,
            actor_type="user",
            merchant_id=membership.merchant_id,
            action="disbursement.requested",
            resource_type="disbursement",
            resource_id=uuid.UUID(disbursement["id"]),
            metadata={"method": payload.method.value},
        )
        return status.HTTP_202_ACCEPTED, disbursement

    _status_code, body = await run_idempotent(
        client,
        merchant_id=membership.merchant_id,
        endpoint="POST /v1/merchant/withdrawals",
        idempotency_key=idempotency_key,
        request_payload=payload.model_dump(mode="json"),
        handler=_handler,
    )
    return APIResponse(data=DisbursementResponse(**body))


# --- Transactions ---------------------------------------------------------


@router.get("/transactions", response_model=APIResponse[list[TransactionResponse]])
def list_my_transactions(
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
):
    client = get_supabase_admin()
    rows, total = list_for_merchant(client, "transactions", merchant_id=membership.merchant_id, pagination=pagination)
    data = [TransactionResponse(**row) for row in rows]
    return APIResponse(data=data, meta=build_page_meta(pagination, total))


@router.get("/transactions/{reference}", response_model=APIResponse[TransactionResponse])
def get_my_transaction_by_reference(
    reference: str,
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
):
    """By the human-readable reference (TXN-...), not the internal UUID id
    — the existing /v1/merchants/{id}/transactions/{transaction_id} route
    only supports lookup by id; this is new."""
    client = get_supabase_admin()
    row = execute_maybe_single(
        client.table("transactions")
        .select("*")
        .eq("merchant_id", str(membership.merchant_id))
        .eq("reference", reference)
        .maybe_single()
    )
    if not row:
        raise NotFoundError("Transaction not found")
    return APIResponse(data=TransactionResponse(**row))


# --- API keys ---------------------------------------------------------------


def _generate_api_key(environment: str) -> tuple[str, str]:
    token = secrets.token_urlsafe(24)
    plaintext = f"inf_{environment}_{token}"
    prefix = plaintext[: len(f"inf_{environment}_") + 6]
    return plaintext, prefix


@router.get("/api-keys", response_model=APIResponse[list[ApiKeyResponse]])
def list_my_api_keys(
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_DEVELOPER))],
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
):
    client = get_supabase_admin()
    rows, total = list_for_merchant(client, "api_keys", merchant_id=membership.merchant_id, pagination=pagination)
    data = [ApiKeyResponse(**row) for row in rows]
    return APIResponse(data=data, meta=build_page_meta(pagination, total))


@router.post("/api-keys", response_model=APIResponse[ApiKeyCreateResponse], status_code=status.HTTP_201_CREATED)
def create_my_api_key(
    payload: ApiKeyCreate,
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_DEVELOPER))],
):
    plaintext, prefix = _generate_api_key(payload.environment)
    client = get_supabase_admin()

    row = insert_row(
        client,
        "api_keys",
        {
            "merchant_id": str(membership.merchant_id),
            "name": payload.name,
            "environment": payload.environment,
            "key_prefix": prefix,
            "hashed_key": hash_api_key(plaintext),
            "scopes": payload.scopes,
            "status": "active",
            "created_by": str(membership.user_id),
        },
    )
    write_audit_log(
        client,
        actor_id=membership.user_id,
        actor_type="user",
        merchant_id=membership.merchant_id,
        action="api_key.created",
        resource_type="api_key",
        resource_id=uuid.UUID(row["id"]),
        metadata={"environment": payload.environment, "scopes": payload.scopes},
    )
    return APIResponse(
        data=ApiKeyCreateResponse(
            id=row["id"],
            name=row["name"],
            environment=row["environment"],
            key_prefix=row["key_prefix"],
            scopes=row["scopes"],
            plaintext_key=plaintext,
            created_at=row["created_at"],
        )
    )


@router.patch("/api-keys/{api_key_id}/revoke", response_model=APIResponse[ApiKeyResponse])
def revoke_my_api_key(
    api_key_id: uuid.UUID,
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_DEVELOPER))],
):
    client = get_supabase_admin()
    row = update_row(
        client,
        "api_keys",
        api_key_id,
        {"status": "revoked", "revoked_at": datetime.now(timezone.utc).isoformat()},
        merchant_id=membership.merchant_id,
    )
    if not row:
        raise NotFoundError("API key not found")

    write_audit_log(
        client,
        actor_id=membership.user_id,
        actor_type="user",
        merchant_id=membership.merchant_id,
        action="api_key.revoked",
        resource_type="api_key",
        resource_id=api_key_id,
    )
    return APIResponse(data=ApiKeyResponse(**row))


# --- Risk monitoring ---------------------------------------------------------


@router.get("/risk-alerts", response_model=APIResponse[list[FraudAlertResponse]])
def list_my_risk_alerts(
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
):
    client = get_supabase_admin()
    rows, total = list_for_merchant(client, "fraud_alerts", merchant_id=membership.merchant_id, pagination=pagination)
    data = [FraudAlertResponse(**row) for row in rows]
    return APIResponse(data=data, meta=build_page_meta(pagination, total))


# --- Document requests --------------------------------------------------------


@router.get("/document-requests", response_model=APIResponse[list[DocumentRequestResponse]])
def list_my_document_requests(
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
):
    client = get_supabase_admin()
    rows = document_requests_service.list_document_requests_for_merchant(client, membership.merchant_id)
    return APIResponse(data=[DocumentRequestResponse(**row) for row in rows])


@router.post("/document-requests/{request_id}/submit", response_model=APIResponse[DocumentRequestResponse])
async def submit_document_request(
    request_id: uuid.UUID,
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
    document_label: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
):
    client = get_supabase_admin()
    request = get_by_id(client, "merchant_document_requests", request_id)
    if not request or request["merchant_id"] != str(membership.merchant_id):
        raise NotFoundError("Document request not found")

    await document_requests_service.register_document_request_file(
        client,
        request_id=request_id,
        merchant_id=membership.merchant_id,
        document_label=document_label,
        file=file,
        uploaded_by=membership.user_id,
    )
    updated = document_requests_service.mark_document_request_submitted(
        client, request_id=request_id, merchant_id=membership.merchant_id
    )
    return APIResponse(data=DocumentRequestResponse(**updated))


# --- Disputes ------------------------------------------------------------------


@router.get("/disputes", response_model=APIResponse[list[DisputeResponse]])
def list_my_disputes(
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
):
    client = get_supabase_admin()
    rows = disputes_service.list_disputes_for_merchant(client, membership.merchant_id)
    return APIResponse(data=[DisputeResponse(**row) for row in rows])


@router.get("/disputes/{dispute_id}", response_model=APIResponse[dict])
def get_my_dispute(
    dispute_id: uuid.UUID,
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
):
    client = get_supabase_admin()
    dispute = get_by_id(client, "disputes", dispute_id)
    if not dispute or dispute.get("merchant_id") != str(membership.merchant_id):
        raise NotFoundError("Dispute not found")
    return APIResponse(data=disputes_service.get_dispute_with_messages(client, dispute_id))


@router.post("/disputes/{dispute_id}/respond", response_model=APIResponse[dict])
def respond_to_my_dispute(
    dispute_id: uuid.UUID,
    payload: DisputeMessageCreate,
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
):
    client = get_supabase_admin()
    result = disputes_service.respond_to_dispute(
        client, dispute_id=dispute_id, merchant_id=membership.merchant_id, sender_id=membership.user_id, body=payload.body
    )
    return APIResponse(data=result)


@router.post("/disputes/{dispute_id}/accept-refund", response_model=APIResponse[RefundResponse])
def accept_refund_for_my_dispute(
    dispute_id: uuid.UUID,
    payload: RequestRefundInput,
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_ONLY))],
):
    client = get_supabase_admin()
    refund = disputes_service.accept_refund(
        client, dispute_id=dispute_id, merchant_id=membership.merchant_id, amount=payload.amount
    )
    return APIResponse(data=RefundResponse(**refund))


# --- Notifications ---------------------------------------------------------


@router.get("/notifications", response_model=APIResponse[list[NotificationResponse]])
def list_my_notifications(
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
):
    client = get_supabase_admin()
    rows = (
        client.table("notifications")
        .select("*")
        .eq("merchant_id", str(membership.merchant_id))
        .order("created_at", desc=True)
        .execute()
    ).data or []
    return APIResponse(data=[NotificationResponse(**row) for row in rows])
