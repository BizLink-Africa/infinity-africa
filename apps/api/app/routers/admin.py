"""Platform-wide Super Admin dashboard reads — /v1/admin/*.

Every route here is `require_super_admin`-gated and reads across ALL
merchants (no merchant_id scoping) — distinct from the existing
merchant-scoped routers (payment_links.py, invoices.py, collections.py,
transactions.py, disbursements.py) which stay as they are. List endpoints
follow routers/merchants.py::list_merchants' exact pattern: inline
`.select("*", count="exact").order(...).range(...)`, not services/crud.py's
merchant-scoped helpers (these queries have no merchant_id to scope by).

Onboarding review (GET/POST /v1/admin/onboarding/*) lives in
routers/admin_onboarding.py, not here — untouched by this router.
"""

import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.auth import require_super_admin
from app.core.errors import NotFoundError
from app.core.pagination import PaginationParams, build_page_meta, pagination_params
from app.database.session import get_supabase_admin
from app.schemas.admin import (
    AdminAuditLogResponse,
    AdminCollectionResponse,
    AdminInvoiceResponse,
    AdminMerchantResponse,
    AdminMerchantUserResponse,
    AdminOverviewResponse,
    AdminPaymentLinkResponse,
    AdminTransactionResponse,
    AdminWebhookEventResponse,
    AdminWithdrawalResponse,
)
from app.schemas.auth import AuthenticatedUser
from app.schemas.common import APIResponse
from app.services.admin_directory import batch_merchant_names, batch_user_profiles
from app.services.admin_overview import get_admin_overview
from app.services.audit import write_audit_log
from app.services.checkout_reconciliation import refresh_checkout_collection_status
from app.services.crud import get_by_id
from app.services.ledger import get_wallet_balance

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview", response_model=APIResponse[AdminOverviewResponse])
def get_overview(_admin: Annotated[AuthenticatedUser, Depends(require_super_admin)]):
    client = get_supabase_admin()
    return APIResponse(data=AdminOverviewResponse(**get_admin_overview(client)))


@router.get("/merchants", response_model=APIResponse[list[AdminMerchantResponse]])
def list_admin_merchants(
    _admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
):
    client = get_supabase_admin()
    result = (
        client.table("merchants")
        .select("*", count="exact")
        .order("created_at", desc=True)
        .range(pagination.start, pagination.end)
        .execute()
    )
    merchants = result.data or []
    merchant_ids = {m["id"] for m in merchants}

    submissions: list[dict] = []
    owner_user_id_by_merchant: dict[str, str] = {}
    if merchant_ids:
        submissions = (
            client.table("onboarding_submissions")
            .select("merchant_id, nature_of_business, physical_address")
            .in_("merchant_id", list(merchant_ids))
            .execute()
        ).data or []

        memberships = (
            client.table("merchant_users")
            .select("merchant_id, user_id")
            .in_("merchant_id", list(merchant_ids))
            .eq("role", "MERCHANT_ADMIN")
            .eq("status", "active")
            .execute()
        ).data or []
        owner_user_id_by_merchant = {m["merchant_id"]: m["user_id"] for m in memberships}

    submission_by_merchant = {s["merchant_id"]: s for s in submissions}
    profiles = batch_user_profiles(client, set(owner_user_id_by_merchant.values()))

    data = []
    for merchant in merchants:
        submission = submission_by_merchant.get(merchant["id"])
        owner_user_id = owner_user_id_by_merchant.get(merchant["id"])
        profile = profiles.get(owner_user_id, {}) if owner_user_id else {}
        data.append(
            AdminMerchantResponse(
                merchant_id=merchant["id"],
                business_name=merchant["business_name"],
                owner_name=profile.get("full_name"),
                email=merchant["contact_email"],
                contact_phone=merchant.get("contact_phone"),
                nature_of_business=submission["nature_of_business"] if submission else None,
                physical_address=submission["physical_address"] if submission else None,
                account_status=merchant["status"],
                available_balance=get_wallet_balance(
                    client, merchant_id=uuid.UUID(merchant["id"]), currency=merchant["currency"]
                ),
                created_at=merchant["created_at"],
            )
        )
    return APIResponse(data=data, meta=build_page_meta(pagination, result.count or 0))


@router.get("/merchant-users", response_model=APIResponse[list[AdminMerchantUserResponse]])
def list_admin_merchant_users(
    _admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
):
    client = get_supabase_admin()
    result = (
        client.table("merchant_users")
        .select("*", count="exact")
        .order("created_at", desc=True)
        .range(pagination.start, pagination.end)
        .execute()
    )
    rows = result.data or []
    merchant_names = batch_merchant_names(client, {r["merchant_id"] for r in rows})
    profiles = batch_user_profiles(client, {r["user_id"] for r in rows})

    data = [
        AdminMerchantUserResponse(
            user_id=row["user_id"],
            merchant_id=row["merchant_id"],
            merchant_name=merchant_names.get(row["merchant_id"], ""),
            full_name=profiles.get(row["user_id"], {}).get("full_name"),
            email=profiles.get(row["user_id"], {}).get("email"),
            role=row["role"],
            status=row["status"],
            created_at=row["created_at"],
        )
        for row in rows
    ]
    return APIResponse(data=data, meta=build_page_meta(pagination, result.count or 0))


@router.get("/payment-links", response_model=APIResponse[list[AdminPaymentLinkResponse]])
def list_admin_payment_links(
    _admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
):
    client = get_supabase_admin()
    result = (
        client.table("payment_links")
        .select("*", count="exact")
        .order("created_at", desc=True)
        .range(pagination.start, pagination.end)
        .execute()
    )
    rows = result.data or []
    merchant_names = batch_merchant_names(client, {r["merchant_id"] for r in rows})

    data = [
        AdminPaymentLinkResponse(
            link_id=row["id"],
            merchant_id=row["merchant_id"],
            merchant_name=merchant_names.get(row["merchant_id"], ""),
            customer_name=row.get("customer_name"),
            customer_phone=row.get("customer_phone"),
            amount=row["amount"],
            currency=row["currency"],
            status=row["status"],
            expires_at=row.get("expires_at"),
            created_at=row["created_at"],
        )
        for row in rows
    ]
    return APIResponse(data=data, meta=build_page_meta(pagination, result.count or 0))


@router.get("/invoices", response_model=APIResponse[list[AdminInvoiceResponse]])
def list_admin_invoices(
    _admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
):
    client = get_supabase_admin()
    result = (
        client.table("invoices")
        .select("*", count="exact")
        .order("created_at", desc=True)
        .range(pagination.start, pagination.end)
        .execute()
    )
    rows = result.data or []
    merchant_names = batch_merchant_names(client, {r["merchant_id"] for r in rows})

    data = [
        AdminInvoiceResponse(
            invoice_id=row["id"],
            invoice_number=row["invoice_number"],
            merchant_id=row["merchant_id"],
            merchant_name=merchant_names.get(row["merchant_id"], ""),
            customer_name=row.get("customer_name"),
            customer_phone=row.get("customer_phone"),
            total_amount=row["total_amount"],
            status=row["status"],
            due_date=row["due_date"],
            created_at=row["created_at"],
        )
        for row in rows
    ]
    return APIResponse(data=data, meta=build_page_meta(pagination, result.count or 0))


@router.get("/collections", response_model=APIResponse[list[AdminCollectionResponse]])
def list_admin_collections(
    _admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
):
    client = get_supabase_admin()
    result = (
        client.table("collections")
        .select("*", count="exact")
        .order("created_at", desc=True)
        .range(pagination.start, pagination.end)
        .execute()
    )
    rows = result.data or []
    merchant_names = batch_merchant_names(client, {r["merchant_id"] for r in rows})

    # Selcom Checkout wallet-push collections carry their own order_id on
    # the *linked* checkout_orders row, not on collections itself —
    # batched in one query rather than N+1 per row.
    checkout_order_ids = {r["checkout_order_id"] for r in rows if r.get("checkout_order_id")}
    order_ids_by_checkout_order_id: dict[str, str] = {}
    if checkout_order_ids:
        orders_result = (
            client.table("checkout_orders").select("id,order_id").in_("id", list(checkout_order_ids)).execute()
        )
        order_ids_by_checkout_order_id = {o["id"]: o["order_id"] for o in orders_result.data or []}

    data = [
        AdminCollectionResponse(
            collection_id=row["id"],
            merchant_id=row["merchant_id"],
            merchant_name=merchant_names.get(row["merchant_id"], ""),
            method=row["method"],
            amount=row["amount"],
            currency=row["currency"],
            phone=row.get("customer_phone"),
            provider_reference=row.get("provider_reference"),
            status=row["status"],
            created_at=row["created_at"],
            order_id=order_ids_by_checkout_order_id.get(row.get("checkout_order_id")),
            provider_transid=row.get("provider_transid"),
            channel=row.get("channel"),
            provider_payment_status=row.get("provider_payment_status"),
            failure_reason=row.get("failure_reason"),
        )
        for row in rows
    ]
    return APIResponse(data=data, meta=build_page_meta(pagination, result.count or 0))


@router.post("/collections/{collection_id}/refresh-status", response_model=APIResponse[AdminCollectionResponse])
async def refresh_admin_collection_status(
    collection_id: uuid.UUID,
    admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
):
    """Super Admin equivalent of
    POST /v1/merchant/collections/{id}/refresh-status — not scoped to any
    one merchant, since this router reads across all of them (see module
    docstring)."""
    client = get_supabase_admin()
    collection = get_by_id(client, "collections", collection_id)
    if not collection:
        raise NotFoundError("Collection not found")

    resolved = await refresh_checkout_collection_status(client, collection_id=collection_id)

    write_audit_log(
        client,
        actor_id=admin.id,
        merchant_id=uuid.UUID(resolved["merchant_id"]),
        action="collection.status_refreshed",
        resource_type="collection",
        resource_id=collection_id,
        metadata={"status": resolved["status"]},
    )

    merchant_names = batch_merchant_names(client, {resolved["merchant_id"]})
    order_id = None
    if resolved.get("checkout_order_id"):
        order = get_by_id(client, "checkout_orders", uuid.UUID(resolved["checkout_order_id"]))
        order_id = order["order_id"] if order else None

    return APIResponse(
        data=AdminCollectionResponse(
            collection_id=resolved["id"],
            merchant_id=resolved["merchant_id"],
            merchant_name=merchant_names.get(resolved["merchant_id"], ""),
            method=resolved["method"],
            amount=resolved["amount"],
            currency=resolved["currency"],
            phone=resolved.get("customer_phone"),
            provider_reference=resolved.get("provider_reference"),
            status=resolved["status"],
            created_at=resolved["created_at"],
            order_id=order_id,
            provider_transid=resolved.get("provider_transid"),
            channel=resolved.get("channel"),
            provider_payment_status=resolved.get("provider_payment_status"),
            failure_reason=resolved.get("failure_reason"),
        )
    )


@router.get("/withdrawals", response_model=APIResponse[list[AdminWithdrawalResponse]])
def list_admin_withdrawals(
    _admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
    status: Annotated[str | None, Query(description="Filter by disbursement status, e.g. PENDING_ADMIN_APPROVAL")] = None,
    requires_approval: Annotated[bool | None, Query()] = None,
):
    client = get_supabase_admin()
    query = client.table("disbursements").select("*", count="exact")
    if status is not None:
        query = query.eq("status", status)
    if requires_approval is not None:
        query = query.eq("requires_approval", requires_approval)
    result = query.order("created_at", desc=True).range(pagination.start, pagination.end).execute()
    rows = result.data or []
    merchant_names = batch_merchant_names(client, {r["merchant_id"] for r in rows})

    data = [
        AdminWithdrawalResponse(
            withdrawal_id=row["id"],
            merchant_id=row["merchant_id"],
            merchant_name=merchant_names.get(row["merchant_id"], ""),
            method=row["method"],
            amount=row["amount"],
            currency=row["currency"],
            destination=row["destination_name"],
            destination_code=row.get("destination_code"),
            destination_identifier=row["destination_identifier"],
            status=row["status"],
            requires_approval=row["requires_approval"],
            provider_reference=row.get("provider_reference"),
            total_charges=row.get("total_charges") or Decimal(0),
            total_reserved_amount=row.get("total_reserved_amount"),
            recipient_net_amount=row.get("recipient_net_amount"),
            pricing_rule_id=row.get("pricing_rule_id"),
            rejection_reason=row.get("rejection_reason"),
            admin_status_reason=row.get("admin_status_reason"),
            created_at=row["created_at"],
        )
        for row in rows
    ]
    return APIResponse(data=data, meta=build_page_meta(pagination, result.count or 0))


@router.get("/transactions", response_model=APIResponse[list[AdminTransactionResponse]])
def list_admin_transactions(
    _admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
):
    client = get_supabase_admin()
    result = (
        client.table("transactions")
        .select("*", count="exact")
        .order("created_at", desc=True)
        .range(pagination.start, pagination.end)
        .execute()
    )
    rows = result.data or []
    merchant_names = batch_merchant_names(client, {r["merchant_id"] for r in rows})

    data = [
        AdminTransactionResponse(
            transaction_id=row["id"],
            merchant_id=row["merchant_id"],
            merchant_name=merchant_names.get(row["merchant_id"], ""),
            reference=row["reference"],
            type=row["type"],
            method=row["method"],
            gross_amount=row["gross_amount"],
            fee_amount=row["fee_amount"],
            net_amount=row["net_amount"],
            currency=row["currency"],
            status=row["status"],
            created_at=row["created_at"],
        )
        for row in rows
    ]
    return APIResponse(data=data, meta=build_page_meta(pagination, result.count or 0))


@router.get("/webhooks", response_model=APIResponse[list[AdminWebhookEventResponse]])
def list_admin_webhooks(
    _admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
):
    """Inbound provider callback log (selcom_webhook_events) — NOT the
    outbound merchant webhook deliveries table, which already has its own
    per-merchant view at GET /v1/merchants/{merchant_id}/webhooks."""
    client = get_supabase_admin()
    result = (
        client.table("selcom_webhook_events")
        .select("*", count="exact")
        .order("created_at", desc=True)
        .range(pagination.start, pagination.end)
        .execute()
    )
    data = [
        AdminWebhookEventResponse(
            webhook_event_id=row["id"],
            provider=row["provider"],
            event_type=row["event_type"],
            reference=row["event_id"],
            processed_at=row.get("processed_at"),
            created_at=row["created_at"],
            status=row["status"],
        )
        for row in (result.data or [])
    ]
    return APIResponse(data=data, meta=build_page_meta(pagination, result.count or 0))


@router.get("/audit-logs", response_model=APIResponse[list[AdminAuditLogResponse]])
def list_admin_audit_logs(
    _admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
):
    client = get_supabase_admin()
    result = (
        client.table("audit_logs")
        .select("*", count="exact")
        .order("created_at", desc=True)
        .range(pagination.start, pagination.end)
        .execute()
    )
    rows = result.data or []
    actor_ids = {r["actor_id"] for r in rows if r.get("actor_id")}
    profiles = batch_user_profiles(client, actor_ids)

    data = []
    for row in rows:
        profile = profiles.get(row.get("actor_id"), {})
        actor = profile.get("full_name") or profile.get("email")
        data.append(
            AdminAuditLogResponse(
                audit_id=row["id"],
                actor=actor,
                action=row["action"],
                entity_type=row["resource_type"],
                entity_id=row.get("resource_id"),
                metadata=row.get("metadata") or {},
                ip_address=row.get("ip_address"),
                created_at=row["created_at"],
            )
        )
    return APIResponse(data=data, meta=build_page_meta(pagination, result.count or 0))
