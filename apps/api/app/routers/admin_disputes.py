"""Super Admin dispute/chargeback review and refund actions —
/v1/admin/disputes. Own file, matching admin.py's own stated convention of
splitting out review workflows rather than growing admin.py itself.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth import require_super_admin
from app.core.errors import NotFoundError
from app.database.session import get_supabase_admin
from app.schemas.auth import AuthenticatedUser
from app.schemas.common import APIResponse
from app.schemas.disputes import (
    AdminDisputeResponse,
    DisputeStatusUpdate,
    RequestRefundInput,
)
from app.schemas.refunds import RefundResponse, RefundStatusUpdate
from app.services import disputes_service
from app.services.admin_directory import batch_merchant_codes, batch_merchant_names

router = APIRouter(prefix="/admin", tags=["admin-disputes"])


@router.get("/disputes", response_model=APIResponse[list[AdminDisputeResponse]])
def list_disputes(_admin: Annotated[AuthenticatedUser, Depends(require_super_admin)]):
    client = get_supabase_admin()
    rows = disputes_service.list_all_disputes(client)
    ids = {r["merchant_id"] for r in rows if r.get("merchant_id")}
    names = batch_merchant_names(client, ids)
    codes = batch_merchant_codes(client, ids)
    data = [
        AdminDisputeResponse.from_row(
            row, merchant_name=names.get(row.get("merchant_id")), merchant_code=codes.get(row.get("merchant_id"))
        )
        for row in rows
    ]
    return APIResponse(data=data)


@router.get("/disputes/{dispute_id}", response_model=APIResponse[dict])
def get_dispute(dispute_id: uuid.UUID, _admin: Annotated[AuthenticatedUser, Depends(require_super_admin)]):
    client = get_supabase_admin()
    return APIResponse(data=disputes_service.get_dispute_with_messages(client, dispute_id))


@router.patch("/disputes/{dispute_id}/status", response_model=APIResponse[AdminDisputeResponse])
def update_dispute_status(
    dispute_id: uuid.UUID,
    payload: DisputeStatusUpdate,
    admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
):
    client = get_supabase_admin()
    updated = disputes_service.update_dispute_status(
        client, dispute_id=dispute_id, status=payload.status, note=payload.note, admin_id=admin.id
    )
    ids = {updated["merchant_id"]} if updated.get("merchant_id") else set()
    names = batch_merchant_names(client, ids)
    codes = batch_merchant_codes(client, ids)
    return APIResponse(
        data=AdminDisputeResponse.from_row(
            updated, merchant_name=names.get(updated.get("merchant_id")), merchant_code=codes.get(updated.get("merchant_id"))
        )
    )


@router.post("/disputes/{dispute_id}/request-refund", response_model=APIResponse[RefundResponse])
def request_refund(
    dispute_id: uuid.UUID,
    payload: RequestRefundInput,
    _admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
):
    client = get_supabase_admin()
    refund = disputes_service.admin_request_refund(client, dispute_id=dispute_id, amount=payload.amount)
    return APIResponse(data=RefundResponse(**refund))


@router.patch("/disputes/{dispute_id}/refund-status", response_model=APIResponse[RefundResponse])
def update_refund_status(
    dispute_id: uuid.UUID,
    payload: RefundStatusUpdate,
    _admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
):
    """The gap the spec's literal endpoint list didn't cover: Part 8 requires
    "Admin can mark refund status based on provider/manual confirmation" but
    no endpoint for it was listed alongside request-refund/accept-refund.
    Resolves the most recent refund against this dispute — in practice a
    dispute has at most one refund in flight at a time."""
    client = get_supabase_admin()
    rows = (
        client.table("refunds")
        .select("id")
        .eq("dispute_id", str(dispute_id))
        .order("created_at", desc=True)
        .execute()
    ).data or []
    if not rows:
        raise NotFoundError("No refund found for this dispute")

    updated = disputes_service.update_refund_status(
        client, refund_id=uuid.UUID(rows[0]["id"]), status=payload.status, provider_reference=payload.provider_reference
    )
    return APIResponse(data=RefundResponse(**updated))
