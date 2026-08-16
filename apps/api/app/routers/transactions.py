import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth import (
    authorize_merchant_action,
    get_authenticated_caller,
    require_api_key_scope,
    require_role,
)
from app.core.errors import NotFoundError
from app.core.pagination import PaginationParams, build_page_meta, pagination_params
from app.database.session import get_supabase_admin
from app.schemas.auth import AuthenticatedCaller, AuthenticatedUser
from app.schemas.common import APIResponse
from app.schemas.enums import UserRole
from app.schemas.transactions import TransactionResponse
from app.services.crud import execute_maybe_single, get_for_merchant, list_for_merchant

router = APIRouter(prefix="/merchants/{merchant_id}/transactions", tags=["transactions"])
by_reference_router = APIRouter(prefix="/transactions", tags=["transactions"])

_DASHBOARD_ROLES = (UserRole.MERCHANT_ADMIN, UserRole.MERCHANT_STAFF)


@router.get("", response_model=APIResponse[list[TransactionResponse]])
def list_transactions(
    merchant_id: uuid.UUID,
    _actor: Annotated[AuthenticatedUser, Depends(require_role(*_DASHBOARD_ROLES))],
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
):
    """Read-only unified ledger — every write comes from apps/api's own
    services (collections/disbursements), never directly from a client."""
    client = get_supabase_admin()
    rows, total = list_for_merchant(client, "transactions", merchant_id=merchant_id, pagination=pagination)
    data = [TransactionResponse(**row) for row in rows]
    return APIResponse(data=data, meta=build_page_meta(pagination, total))


@router.get("/{transaction_id}", response_model=APIResponse[TransactionResponse])
def get_transaction(
    merchant_id: uuid.UUID,
    transaction_id: uuid.UUID,
    _actor: Annotated[AuthenticatedUser, Depends(require_role(*_DASHBOARD_ROLES))],
):
    client = get_supabase_admin()
    row = get_for_merchant(client, "transactions", merchant_id=merchant_id, row_id=transaction_id)
    if not row:
        raise NotFoundError("Transaction not found")
    return APIResponse(data=TransactionResponse(**row))


@by_reference_router.get("/{reference}", response_model=APIResponse[TransactionResponse])
def get_transaction_by_reference(
    reference: str,
    caller: Annotated[AuthenticatedCaller, Depends(get_authenticated_caller)],
):
    """Flat, API-key-friendly lookup by the human-readable reference
    (TXN-...) — a merchant's own backend calling with an API key has no
    merchant_id to put in a path segment, unlike the dashboard-only
    /v1/merchants/{id}/transactions/{transaction_id} route above (which
    looks up by internal UUID id, not this reference string)."""
    client = get_supabase_admin()
    row = execute_maybe_single(
        client.table("transactions").select("*").eq("reference", reference).maybe_single()
    )
    if not row:
        raise NotFoundError("Transaction not found")

    authorize_merchant_action(caller, uuid.UUID(row["merchant_id"]), *_DASHBOARD_ROLES)
    require_api_key_scope(caller, "transactions:read")

    return APIResponse(data=TransactionResponse(**row))
