import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.auth import require_role, require_super_admin
from app.core.errors import NotFoundError, ValidationAPIError
from app.core.pagination import PaginationParams, build_page_meta, pagination_params
from app.database.session import get_supabase_admin
from app.schemas.auth import AuthenticatedUser
from app.schemas.common import APIResponse
from app.schemas.enums import MERCHANT_ROLES, UserRole
from app.schemas.merchants import (
    MerchantCreate,
    MerchantProfileUpdate,
    MerchantResponse,
    MerchantStatusUpdate,
)
from app.services.audit import write_audit_log
from app.services.crud import get_by_id, insert_row, update_row
from app.services.merchant_code import generate_merchant_code

router = APIRouter(prefix="/merchants", tags=["merchants"])


@router.post("", response_model=APIResponse[MerchantResponse], status_code=status.HTTP_201_CREATED)
def create_merchant(
    payload: MerchantCreate,
    admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
):
    """Onboard a new merchant. Super admin only — self-serve signup isn't built yet."""
    client = get_supabase_admin()
    data = payload.model_dump(mode="json")
    data["status"] = "pending"
    data["kyc_status"] = "unverified"
    data["merchant_code"] = generate_merchant_code(client)
    row = insert_row(client, "merchants", data)

    write_audit_log(
        client,
        actor_id=admin.id,
        action="merchant.created",
        resource_type="merchant",
        resource_id=uuid.UUID(row["id"]),
    )

    return APIResponse(data=MerchantResponse(**row))


@router.get("", response_model=APIResponse[list[MerchantResponse]])
def list_merchants(
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

    data = [MerchantResponse(**row) for row in (result.data or [])]
    return APIResponse(data=data, meta=build_page_meta(pagination, result.count or 0))


@router.get("/{merchant_id}", response_model=APIResponse[MerchantResponse])
def get_merchant(
    merchant_id: uuid.UUID,
    _actor: Annotated[AuthenticatedUser, Depends(require_role(*MERCHANT_ROLES))],
):
    client = get_supabase_admin()
    row = get_by_id(client, "merchants", merchant_id)
    if not row:
        raise NotFoundError("Merchant not found")

    return APIResponse(data=MerchantResponse(**row))


@router.patch("/{merchant_id}", response_model=APIResponse[MerchantResponse])
def update_merchant_profile(
    merchant_id: uuid.UUID,
    payload: MerchantProfileUpdate,
    actor: Annotated[AuthenticatedUser, Depends(require_role(UserRole.MERCHANT_ADMIN))],
):
    client = get_supabase_admin()
    updates = payload.model_dump(mode="json", exclude_unset=True)
    if not updates:
        raise ValidationAPIError("No fields to update")

    row = update_row(client, "merchants", merchant_id, updates)
    if not row:
        raise NotFoundError("Merchant not found")

    write_audit_log(
        client,
        actor_id=actor.id,
        merchant_id=merchant_id,
        action="merchant.updated",
        resource_type="merchant",
        resource_id=merchant_id,
        metadata={"fields": list(updates)},
    )

    return APIResponse(data=MerchantResponse(**row))


@router.patch("/{merchant_id}/status", response_model=APIResponse[MerchantResponse])
def update_merchant_status(
    merchant_id: uuid.UUID,
    payload: MerchantStatusUpdate,
    admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
):
    """Approve, suspend, or update KYC status. Super admin only."""
    client = get_supabase_admin()
    updates = payload.model_dump(mode="json", exclude_unset=True)
    if not updates:
        raise ValidationAPIError("No fields to update")

    row = update_row(client, "merchants", merchant_id, updates)
    if not row:
        raise NotFoundError("Merchant not found")

    write_audit_log(
        client,
        actor_id=admin.id,
        merchant_id=merchant_id,
        action="merchant.status_updated",
        resource_type="merchant",
        resource_id=merchant_id,
        metadata=updates,
    )

    return APIResponse(data=MerchantResponse(**row))
