"""Invoices: itemized bills a merchant sends a customer, payable via a
generated "Pay Now" payment link (see generate_invoice_payment_link below).

Flat resource routes — there's no merchant_id path segment, matching the
payment_links/collections pattern: the caller's merchant is resolved from
their API key, or checked against merchant_id in the request body/a fetched
row for a dashboard JWT caller — see app.auth.get_authenticated_caller /
authorize_merchant_action.
"""

import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.auth import (
    authorize_merchant_action,
    get_authenticated_caller,
    require_api_key_scope,
)
from app.core.errors import ConflictError, NotFoundError, ValidationAPIError
from app.core.pagination import PaginationParams, build_page_meta, pagination_params
from app.core.references import generate_reference
from app.database.session import get_supabase_admin
from app.schemas.auth import AuthenticatedCaller
from app.schemas.common import APIResponse
from app.schemas.enums import CollectionMethod, UserRole
from app.schemas.invoices import (
    InvoiceCreate,
    InvoiceItemResponse,
    InvoiceResponse,
    InvoiceUpdate,
)
from app.schemas.payment_links import PaymentLinkResponse
from app.services.audit import write_audit_log
from app.services.crud import get_by_id, insert_row, list_for_merchant, update_row
from app.services.payment_links import (
    build_public_url,
    generate_public_slug,
    get_with_effective_status,
)

router = APIRouter(prefix="/invoices", tags=["invoices"])

_DASHBOARD_ROLES = (UserRole.MERCHANT_ADMIN, UserRole.MERCHANT_STAFF)

# Only an invoice the customer has actually been sent can be paid — a DRAFT
# is still merchant-side-only, and PAID/CANCELLED have nothing left to pay.
_PAYABLE_STATUSES = ("SENT", "PARTIALLY_PAID", "OVERDUE")


def _fetch_items(client, invoice_id: uuid.UUID) -> list[dict]:
    result = (
        client.table("invoice_items")
        .select("*")
        .eq("invoice_id", str(invoice_id))
        .order("sort_order")
        .execute()
    )
    return result.data or []


def _to_response(client, row: dict) -> InvoiceResponse:
    items = _fetch_items(client, uuid.UUID(row["id"]))
    return InvoiceResponse(**row, items=[InvoiceItemResponse(**item) for item in items])


def _to_payment_link_response(row: dict) -> PaymentLinkResponse:
    return PaymentLinkResponse(**row, public_url=build_public_url(row["public_slug"]))


@router.post("", response_model=APIResponse[InvoiceResponse], status_code=status.HTTP_201_CREATED)
def create_invoice(
    payload: InvoiceCreate,
    caller: Annotated[AuthenticatedCaller, Depends(get_authenticated_caller)],
):
    """Callable from the dashboard (JWT) or a merchant's own backend (API key)."""
    authorize_merchant_action(caller, payload.merchant_id, *_DASHBOARD_ROLES)
    require_api_key_scope(caller, "invoices:write")
    client = get_supabase_admin()

    subtotal = sum((item.quantity * item.unit_price for item in payload.items), Decimal(0))
    total_amount = subtotal + payload.tax_amount - payload.discount_amount
    if total_amount < 0:
        raise ValidationAPIError("Total amount cannot be negative")

    invoice_data = payload.model_dump(mode="json", exclude={"items"})
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
        actor_id=caller.actor_id,
        actor_type=caller.actor_type,
        merchant_id=payload.merchant_id,
        action="invoice.created",
        resource_type="invoice",
        resource_id=uuid.UUID(invoice_id),
    )

    return APIResponse(data=_to_response(client, invoice))


@router.get("", response_model=APIResponse[list[InvoiceResponse]])
def list_invoices(
    merchant_id: Annotated[uuid.UUID, Query(description="The merchant to list invoices for")],
    caller: Annotated[AuthenticatedCaller, Depends(get_authenticated_caller)],
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
):
    authorize_merchant_action(caller, merchant_id, *_DASHBOARD_ROLES)
    require_api_key_scope(caller, "invoices:read")
    client = get_supabase_admin()
    rows, total = list_for_merchant(client, "invoices", merchant_id=merchant_id, pagination=pagination)
    data = [_to_response(client, row) for row in rows]
    return APIResponse(data=data, meta=build_page_meta(pagination, total))


@router.get("/{invoice_id}", response_model=APIResponse[InvoiceResponse])
def get_invoice(
    invoice_id: uuid.UUID,
    caller: Annotated[AuthenticatedCaller, Depends(get_authenticated_caller)],
):
    client = get_supabase_admin()
    row = get_by_id(client, "invoices", invoice_id)
    if not row:
        raise NotFoundError("Invoice not found")

    authorize_merchant_action(caller, uuid.UUID(row["merchant_id"]), *_DASHBOARD_ROLES)
    require_api_key_scope(caller, "invoices:read")
    return APIResponse(data=_to_response(client, row))


@router.patch("/{invoice_id}", response_model=APIResponse[InvoiceResponse])
def update_invoice(
    invoice_id: uuid.UUID,
    payload: InvoiceUpdate,
    caller: Annotated[AuthenticatedCaller, Depends(get_authenticated_caller)],
):
    """Only a DRAFT invoice can be edited — once SENT, its amounts are what
    the customer was already shown."""
    client = get_supabase_admin()
    row = get_by_id(client, "invoices", invoice_id)
    if not row:
        raise NotFoundError("Invoice not found")

    merchant_id = uuid.UUID(row["merchant_id"])
    authorize_merchant_action(caller, merchant_id, *_DASHBOARD_ROLES)
    require_api_key_scope(caller, "invoices:write")

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
        actor_id=caller.actor_id,
        actor_type=caller.actor_type,
        merchant_id=merchant_id,
        action="invoice.updated",
        resource_type="invoice",
        resource_id=invoice_id,
    )

    return APIResponse(data=_to_response(client, row))


@router.post("/{invoice_id}/send", response_model=APIResponse[InvoiceResponse])
def send_invoice(
    invoice_id: uuid.UUID,
    caller: Annotated[AuthenticatedCaller, Depends(get_authenticated_caller)],
):
    client = get_supabase_admin()
    row = get_by_id(client, "invoices", invoice_id)
    if not row:
        raise NotFoundError("Invoice not found")

    merchant_id = uuid.UUID(row["merchant_id"])
    authorize_merchant_action(caller, merchant_id, *_DASHBOARD_ROLES)
    require_api_key_scope(caller, "invoices:write")

    if row["status"] != "DRAFT":
        raise ValidationAPIError("Only a draft invoice can be sent")

    row = update_row(client, "invoices", invoice_id, {"status": "SENT"}) or row
    write_audit_log(
        client,
        actor_id=caller.actor_id,
        actor_type=caller.actor_type,
        merchant_id=merchant_id,
        action="invoice.sent",
        resource_type="invoice",
        resource_id=invoice_id,
    )
    return APIResponse(data=_to_response(client, row))


@router.post("/{invoice_id}/payment-link", response_model=APIResponse[PaymentLinkResponse])
def generate_invoice_payment_link(
    invoice_id: uuid.UUID,
    caller: Annotated[AuthenticatedCaller, Depends(get_authenticated_caller)],
):
    """Generates the "Pay Now" payment link a merchant shares with the
    customer to settle this invoice — reuses the existing Payment Links
    module (public checkout at /pay/[public_slug]) rather than the invoice
    having its own separate public checkout. Idempotent in the practical
    sense: calling it again while the previously generated link is still
    ACTIVE just returns that same link instead of creating a second one.

    Resolving the underlying collection is what actually marks the invoice
    PAID/PARTIALLY_PAID — see services/collections.py's
    _apply_collection_success, which looks the invoice up by
    payment_link_id once the link itself is paid.
    """
    client = get_supabase_admin()
    row = get_by_id(client, "invoices", invoice_id)
    if not row:
        raise NotFoundError("Invoice not found")

    merchant_id = uuid.UUID(row["merchant_id"])
    authorize_merchant_action(caller, merchant_id, *_DASHBOARD_ROLES)
    require_api_key_scope(caller, "invoices:write")

    if row["status"] not in _PAYABLE_STATUSES:
        raise ValidationAPIError(
            f"Cannot generate a payment link for an invoice with status {row['status']}; send it first"
        )

    amount_due = Decimal(str(row["total_amount"])) - Decimal(str(row["amount_paid"]))
    if amount_due <= 0:
        raise ValidationAPIError("This invoice has no remaining balance")

    if row.get("payment_link_id"):
        existing = get_with_effective_status(client, uuid.UUID(row["payment_link_id"]))
        if existing and existing["status"] == "ACTIVE":
            return APIResponse(data=_to_payment_link_response(existing))

    link_data = {
        "merchant_id": str(merchant_id),
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
        actor_id=caller.actor_id,
        actor_type=caller.actor_type,
        merchant_id=merchant_id,
        action="invoice.payment_link_generated",
        resource_type="invoice",
        resource_id=invoice_id,
        metadata={"payment_link_id": link["id"]},
    )

    return APIResponse(data=_to_payment_link_response(link))


@router.patch("/{invoice_id}/cancel", response_model=APIResponse[InvoiceResponse])
def cancel_invoice(
    invoice_id: uuid.UUID,
    caller: Annotated[AuthenticatedCaller, Depends(get_authenticated_caller)],
):
    client = get_supabase_admin()
    row = get_by_id(client, "invoices", invoice_id)
    if not row:
        raise NotFoundError("Invoice not found")

    merchant_id = uuid.UUID(row["merchant_id"])
    authorize_merchant_action(caller, merchant_id, *_DASHBOARD_ROLES)
    require_api_key_scope(caller, "invoices:write")

    if row["status"] == "PAID":
        raise ConflictError("A paid invoice cannot be cancelled")

    if row["status"] != "CANCELLED":
        row = update_row(client, "invoices", invoice_id, {"status": "CANCELLED"}) or row
        write_audit_log(
            client,
            actor_id=caller.actor_id,
            actor_type=caller.actor_type,
            merchant_id=merchant_id,
            action="invoice.cancelled",
            resource_type="invoice",
            resource_id=invoice_id,
        )

    return APIResponse(data=_to_response(client, row))
