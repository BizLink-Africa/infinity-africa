"""Disbursements: requesting a payout from a merchant's Infinity Africa balance,
and reading back what's been recorded.

Flat resource routes — there's no merchant_id path segment, matching the
payment_links/invoices/collections pattern: the caller's merchant is
resolved from their API key, or checked against merchant_id in the request
body/a fetched row for a dashboard JWT caller — see
app.auth.get_authenticated_caller / authorize_merchant_action.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, status

from app.auth import (
    authorize_merchant_action,
    get_authenticated_caller,
    require_super_admin,
)
from app.core.errors import NotFoundError
from app.core.pagination import PaginationParams, build_page_meta, pagination_params
from app.database.session import get_supabase_admin
from app.schemas.auth import AuthenticatedCaller, AuthenticatedUser
from app.schemas.common import APIResponse
from app.schemas.disbursements import (
    BankAccountDisbursementRequest,
    DisbursementResponse,
    PhoneDisbursementRequest,
)
from app.schemas.enums import DisbursementMethod, UserRole
from app.services.audit import write_audit_log
from app.services.crud import get_by_id, list_for_merchant
from app.services.disbursements import (
    approve_disbursement,
    execute_disbursement,
    reject_disbursement,
)
from app.services.idempotency import run_idempotent

router = APIRouter(prefix="/disbursements", tags=["disbursements"])

_DASHBOARD_ROLES = (UserRole.MERCHANT_ADMIN, UserRole.MERCHANT_STAFF)

_METHOD_PATHS: dict[DisbursementMethod, str] = {
    DisbursementMethod.SELCOM_PESA: "selcom-pesa",
    DisbursementMethod.MOBILE_MONEY: "mobile-money",
    DisbursementMethod.BANK_ACCOUNT: "bank-account",
}


async def _create_disbursement(
    method: DisbursementMethod,
    payload: PhoneDisbursementRequest | BankAccountDisbursementRequest,
    caller: AuthenticatedCaller,
    idempotency_key: str,
) -> APIResponse[DisbursementResponse]:
    authorize_merchant_action(caller, payload.merchant_id, *_DASHBOARD_ROLES)
    client = get_supabase_admin()

    async def _handler() -> tuple[int, dict]:
        disbursement = await execute_disbursement(
            client,
            merchant_id=payload.merchant_id,
            method=method,
            amount=payload.amount,
            currency=payload.currency,
            destination_name=payload.destination_name,
            destination_identifier=payload.destination_identifier,
            bank_name=getattr(payload, "bank_name", None),
        )
        write_audit_log(
            client,
            actor_id=caller.actor_id,
            actor_type=caller.actor_type,
            merchant_id=payload.merchant_id,
            action="disbursement.requested",
            resource_type="disbursement",
            resource_id=uuid.UUID(disbursement["id"]),
            metadata={"method": method.value},
        )
        return status.HTTP_202_ACCEPTED, disbursement

    _status_code, body = await run_idempotent(
        client,
        merchant_id=payload.merchant_id,
        endpoint=f"POST /v1/disbursements/{_METHOD_PATHS[method]}",
        idempotency_key=idempotency_key,
        request_payload=payload.model_dump(mode="json"),
        handler=_handler,
    )

    return APIResponse(data=DisbursementResponse(**body))


@router.post(
    "/selcom-pesa", response_model=APIResponse[DisbursementResponse], status_code=status.HTTP_202_ACCEPTED
)
async def create_selcom_pesa_disbursement(
    payload: PhoneDisbursementRequest,
    caller: Annotated[AuthenticatedCaller, Depends(get_authenticated_caller)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
):
    return await _create_disbursement(DisbursementMethod.SELCOM_PESA, payload, caller, idempotency_key)


@router.post(
    "/mobile-money", response_model=APIResponse[DisbursementResponse], status_code=status.HTTP_202_ACCEPTED
)
async def create_mobile_money_disbursement(
    payload: PhoneDisbursementRequest,
    caller: Annotated[AuthenticatedCaller, Depends(get_authenticated_caller)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
):
    return await _create_disbursement(DisbursementMethod.MOBILE_MONEY, payload, caller, idempotency_key)


@router.post(
    "/bank-account", response_model=APIResponse[DisbursementResponse], status_code=status.HTTP_202_ACCEPTED
)
async def create_bank_account_disbursement(
    payload: BankAccountDisbursementRequest,
    caller: Annotated[AuthenticatedCaller, Depends(get_authenticated_caller)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
):
    return await _create_disbursement(DisbursementMethod.BANK_ACCOUNT, payload, caller, idempotency_key)


@router.get("", response_model=APIResponse[list[DisbursementResponse]])
def list_disbursements(
    merchant_id: Annotated[uuid.UUID, Query(description="The merchant to list disbursements for")],
    caller: Annotated[AuthenticatedCaller, Depends(get_authenticated_caller)],
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
):
    authorize_merchant_action(caller, merchant_id, *_DASHBOARD_ROLES)
    client = get_supabase_admin()
    rows, total = list_for_merchant(client, "disbursements", merchant_id=merchant_id, pagination=pagination)
    data = [DisbursementResponse(**row) for row in rows]
    return APIResponse(data=data, meta=build_page_meta(pagination, total))


@router.get("/{disbursement_id}", response_model=APIResponse[DisbursementResponse])
def get_disbursement(
    disbursement_id: uuid.UUID,
    caller: Annotated[AuthenticatedCaller, Depends(get_authenticated_caller)],
):
    client = get_supabase_admin()
    row = get_by_id(client, "disbursements", disbursement_id)
    if not row:
        raise NotFoundError("Disbursement not found")

    authorize_merchant_action(caller, uuid.UUID(row["merchant_id"]), *_DASHBOARD_ROLES)
    return APIResponse(data=DisbursementResponse(**row))


@router.post("/{disbursement_id}/approve", response_model=APIResponse[DisbursementResponse])
async def approve_disbursement_route(
    disbursement_id: uuid.UUID,
    admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
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
def reject_disbursement_route(
    disbursement_id: uuid.UUID,
    admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
):
    client = get_supabase_admin()
    disbursement = reject_disbursement(client, disbursement_id=disbursement_id, approver_id=admin.id)

    write_audit_log(
        client,
        actor_id=admin.id,
        merchant_id=uuid.UUID(disbursement["merchant_id"]),
        action="disbursement.rejected",
        resource_type="disbursement",
        resource_id=disbursement_id,
    )

    return APIResponse(data=DisbursementResponse(**disbursement))
