"""Super Admin withdrawal pricing-rule management —
/v1/admin/merchants/{merchant_id}/pricing-rules and
/v1/admin/pricing-rules/*. Own file, matching the established
one-file-per-review-workflow convention (admin_onboarding.py,
admin_disputes.py, admin_risk.py).

Every write here is service_role-only (merchant_pricing_rules has no
insert/update/delete RLS policy — see
supabase/migrations/20260820090000_merchant_pricing_rules.sql); this router
is the only way a rule is ever created, edited, or deactivated.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.auth import require_super_admin
from app.core.errors import NotFoundError
from app.core.time import utc_now_iso
from app.database.session import get_supabase_admin
from app.schemas.auth import AuthenticatedUser
from app.schemas.common import APIResponse
from app.schemas.withdrawals import (
    PricingRuleCreate,
    PricingRuleResponse,
    PricingRuleUpdate,
)
from app.services.crud import get_by_id, insert_row, update_row

router = APIRouter(prefix="/admin", tags=["admin-pricing"])


def _list_rules(client, *, merchant_id: uuid.UUID | None) -> list[dict]:
    query = client.table("merchant_pricing_rules").select("*")
    query = query.eq("merchant_id", str(merchant_id)) if merchant_id else query.is_("merchant_id", "null")
    result = query.order("created_at", desc=True).execute()
    return result.data or []


@router.get("/pricing-rules", response_model=APIResponse[list[PricingRuleResponse]])
def list_platform_pricing_rules(
    _admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
    merchant_id: Annotated[uuid.UUID | None, Query(description="Omit to list platform fallback rules")] = None,
):
    client = get_supabase_admin()
    rows = _list_rules(client, merchant_id=merchant_id)
    return APIResponse(data=[PricingRuleResponse(**row) for row in rows])


@router.post("/pricing-rules/platform-fallback", response_model=APIResponse[PricingRuleResponse])
def create_platform_fallback_pricing_rule(
    payload: PricingRuleCreate,
    admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
):
    client = get_supabase_admin()
    row = insert_row(
        client,
        "merchant_pricing_rules",
        {"merchant_id": None, "created_by": str(admin.id), **_create_rule_fields(payload)},
    )
    return APIResponse(data=PricingRuleResponse(**row))


@router.get("/merchants/{merchant_id}/pricing-rules", response_model=APIResponse[list[PricingRuleResponse]])
def list_merchant_pricing_rules(
    merchant_id: uuid.UUID,
    _admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
):
    client = get_supabase_admin()
    if not get_by_id(client, "merchants", merchant_id):
        raise NotFoundError("Merchant not found")
    rows = _list_rules(client, merchant_id=merchant_id)
    return APIResponse(data=[PricingRuleResponse(**row) for row in rows])


@router.post("/merchants/{merchant_id}/pricing-rules", response_model=APIResponse[PricingRuleResponse])
def create_merchant_pricing_rule(
    merchant_id: uuid.UUID,
    payload: PricingRuleCreate,
    admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
):
    client = get_supabase_admin()
    if not get_by_id(client, "merchants", merchant_id):
        raise NotFoundError("Merchant not found")

    row = insert_row(
        client,
        "merchant_pricing_rules",
        {"merchant_id": str(merchant_id), "created_by": str(admin.id), **_create_rule_fields(payload)},
    )
    return APIResponse(data=PricingRuleResponse(**row))


@router.patch("/pricing-rules/{pricing_rule_id}", response_model=APIResponse[PricingRuleResponse])
def update_pricing_rule(
    pricing_rule_id: uuid.UUID,
    payload: PricingRuleUpdate,
    _admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
):
    client = get_supabase_admin()
    if not get_by_id(client, "merchant_pricing_rules", pricing_rule_id):
        raise NotFoundError("Pricing rule not found")

    fields = _rule_fields(payload, exclude_unset=True)
    if fields:
        row = update_row(client, "merchant_pricing_rules", pricing_rule_id, fields)
    else:
        row = get_by_id(client, "merchant_pricing_rules", pricing_rule_id)
    return APIResponse(data=PricingRuleResponse(**row))


@router.post("/pricing-rules/{pricing_rule_id}/deactivate", response_model=APIResponse[PricingRuleResponse])
def deactivate_pricing_rule(
    pricing_rule_id: uuid.UUID,
    _admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
):
    client = get_supabase_admin()
    if not get_by_id(client, "merchant_pricing_rules", pricing_rule_id):
        raise NotFoundError("Pricing rule not found")

    row = update_row(client, "merchant_pricing_rules", pricing_rule_id, {"is_active": False})
    return APIResponse(data=PricingRuleResponse(**row))


def _rule_fields(payload: PricingRuleCreate | PricingRuleUpdate, *, exclude_unset: bool = False) -> dict:
    return payload.model_dump(mode="json", exclude_unset=exclude_unset)


def _create_rule_fields(payload: PricingRuleCreate) -> dict:
    """Like _rule_fields, but never sends an explicit null for
    effective_from — the column is NOT NULL DEFAULT now() in Postgres;
    omitting it (rather than nulling it out) lets that default apply,
    same as if the field had never been in the request at all."""
    fields = _rule_fields(payload)
    if fields.get("effective_from") is None:
        fields["effective_from"] = utc_now_iso()
    return fields
