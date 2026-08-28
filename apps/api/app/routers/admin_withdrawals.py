"""Super Admin withdrawal review — approve/reject/request-info/refresh-status
plus a batch reconcile action. Own file, not admin.py (which stays a
read-only platform-wide dashboard) or disbursements.py (merchant/API-key-
facing create/list/get only) — matching the one-file-per-review-workflow
convention already used by admin_onboarding.py/admin_disputes.py/admin_risk.py.

Selcom is only ever called from approve_disbursement (via
_reserve_and_run_disbursement_provider) — every route here is
`require_super_admin`-gated, and nothing a merchant does can reach any of
these paths. See app/services/disbursements.py for the state machine.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth import require_super_admin
from app.core.rate_limit import rate_limit
from app.database.session import get_supabase_admin
from app.schemas.auth import AuthenticatedUser
from app.schemas.common import APIResponse
from app.schemas.disbursements import DisbursementResponse
from app.schemas.withdrawals import (
    WithdrawalRejectRequest,
    WithdrawalRequestInfoRequest,
)
from app.services.audit import write_audit_log
from app.services.disbursements import (
    approve_disbursement,
    reconcile_pending_disbursements,
    refresh_disbursement_status,
    reject_disbursement,
    request_more_info,
)

router = APIRouter(prefix="/admin/withdrawals", tags=["admin-withdrawals"])


@router.post("/{disbursement_id}/approve", response_model=APIResponse[DisbursementResponse])
async def approve_withdrawal(
    disbursement_id: uuid.UUID,
    admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
    _rate_limit: Annotated[None, Depends(rate_limit(scope="withdrawal_approval", limit=60, window_seconds=60))],
):
    client = get_supabase_admin()
    disbursement = await approve_disbursement(client, disbursement_id=disbursement_id, approver_id=admin.id)

    write_audit_log(
        client,
        actor_id=admin.id,
        merchant_id=uuid.UUID(disbursement["merchant_id"]),
        action="disbursement.approved",
        resource_type="disbursement",
        resource_id=disbursement_id,
    )

    return APIResponse(data=DisbursementResponse(**disbursement))


@router.post("/{disbursement_id}/reject", response_model=APIResponse[DisbursementResponse])
def reject_withdrawal(
    disbursement_id: uuid.UUID,
    payload: WithdrawalRejectRequest,
    admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
    _rate_limit: Annotated[None, Depends(rate_limit(scope="withdrawal_approval", limit=60, window_seconds=60))],
):
    client = get_supabase_admin()
    disbursement = reject_disbursement(
        client,
        disbursement_id=disbursement_id,
        approver_id=admin.id,
        rejection_reason=payload.rejection_reason,
    )

    write_audit_log(
        client,
        actor_id=admin.id,
        merchant_id=uuid.UUID(disbursement["merchant_id"]),
        action="disbursement.rejected",
        resource_type="disbursement",
        resource_id=disbursement_id,
        metadata={"rejection_reason": payload.rejection_reason},
    )

    return APIResponse(data=DisbursementResponse(**disbursement))


@router.post("/{disbursement_id}/request-info", response_model=APIResponse[DisbursementResponse])
def request_withdrawal_info(
    disbursement_id: uuid.UUID,
    payload: WithdrawalRequestInfoRequest,
    admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
):
    client = get_supabase_admin()
    disbursement = request_more_info(
        client,
        disbursement_id=disbursement_id,
        admin_id=admin.id,
        message=payload.message,
        requested_documents=payload.requested_documents,
    )

    write_audit_log(
        client,
        actor_id=admin.id,
        merchant_id=uuid.UUID(disbursement["merchant_id"]),
        action="disbursement.info_requested",
        resource_type="disbursement",
        resource_id=disbursement_id,
        metadata={"message": payload.message, "requested_documents": payload.requested_documents},
    )

    return APIResponse(data=DisbursementResponse(**disbursement))


@router.post("/{disbursement_id}/refresh-status", response_model=APIResponse[DisbursementResponse])
async def refresh_withdrawal_status(
    disbursement_id: uuid.UUID,
    admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
):
    client = get_supabase_admin()
    disbursement = await refresh_disbursement_status(client, disbursement_id=disbursement_id)

    write_audit_log(
        client,
        actor_id=admin.id,
        merchant_id=uuid.UUID(disbursement["merchant_id"]),
        action="disbursement.status_refreshed",
        resource_type="disbursement",
        resource_id=disbursement_id,
        metadata={"status": disbursement["status"]},
    )

    return APIResponse(data=DisbursementResponse(**disbursement))


@router.post("/reconcile-pending", response_model=APIResponse[dict])
async def reconcile_pending_withdrawals(
    admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
):
    client = get_supabase_admin()
    summary = await reconcile_pending_disbursements(client)

    write_audit_log(
        client,
        actor_id=admin.id,
        action="disbursement.reconcile_pending",
        resource_type="disbursement",
        metadata=summary,
    )

    return APIResponse(data=summary)
