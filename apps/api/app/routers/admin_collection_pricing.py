"""Super Admin COLLECTION pricing-rule management —
/v1/admin/merchants/{merchant_id}/collection-pricing-rules and
/v1/admin/collection-pricing-rules/*. Own file, mirroring
admin_pricing.py (the withdrawal-side sibling, which — per the
2026-08-31 "fees apply to collections only" policy — no longer charges
anything) — same shapes, same precedence model, applied to
merchant_collection_pricing_rules instead.

Every write here is service_role-only (merchant_collection_pricing_rules
has no insert/update/delete RLS policy — see
supabase/migrations/20260831010000_merchant_collection_pricing_rules.sql);
this router is the only way a rule is ever created, edited, activated, or
deactivated. Every write is audit-logged and rate-limited — admin_pricing.py
has neither today; not retrofitted there in this pass, but added here
since collection pricing is the one place a merchant fee is now actually
charged from, making a mistaken/malicious edit here directly
revenue-affecting.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.auth import require_super_admin
from app.core.errors import NotFoundError
from app.core.rate_limit import rate_limit
from app.core.time import utc_now_iso
from app.database.session import get_supabase_admin
from app.schemas.auth import AuthenticatedUser
from app.schemas.collection_pricing import (
    CollectionPricingRuleCreate,
    CollectionPricingRuleResponse,
    CollectionPricingRuleUpdate,
)
from app.schemas.common import APIResponse
from app.services.audit import write_audit_log
from app.services.crud import get_by_id, insert_row, update_row

router = APIRouter(prefix="/admin", tags=["admin-collection-pricing"])

_TABLE = "merchant_collection_pricing_rules"
_WRITE_RATE_LIMIT = Depends(rate_limit(scope="collection_pricing_manage", limit=30, window_seconds=60))


def _list_rules(client, *, merchant_id: uuid.UUID | None) -> list[dict]:
    query = client.table(_TABLE).select("*")
    query = query.eq("merchant_id", str(merchant_id)) if merchant_id else query.is_("merchant_id", "null")
    result = query.order("created_at", desc=True).execute()
    return result.data or []


@router.get("/collection-pricing-rules", response_model=APIResponse[list[CollectionPricingRuleResponse]])
def list_platform_collection_pricing_rules(
    _admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
    merchant_id: Annotated[uuid.UUID | None, Query(description="Omit to list platform fallback rules")] = None,
):
    client = get_supabase_admin()
    rows = _list_rules(client, merchant_id=merchant_id)
    return APIResponse(data=[CollectionPricingRuleResponse(**row) for row in rows])


@router.post("/collection-pricing-rules/platform-fallback", response_model=APIResponse[CollectionPricingRuleResponse])
def create_platform_fallback_collection_pricing_rule(
    payload: CollectionPricingRuleCreate,
    admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
    _rate_limit: Annotated[None, _WRITE_RATE_LIMIT],
):
    client = get_supabase_admin()
    row = insert_row(
        client,
        _TABLE,
        {"merchant_id": None, "created_by": str(admin.id), **_create_rule_fields(payload)},
    )
    write_audit_log(
        client,
        actor_id=admin.id,
        action="collection_pricing_rule.created",
        resource_type="merchant_collection_pricing_rule",
        resource_id=uuid.UUID(row["id"]),
        metadata={"merchant_id": None, "percentage_fee": str(row["percentage_fee"]), "channel": row.get("channel")},
    )
    return APIResponse(data=CollectionPricingRuleResponse(**row))


@router.get(
    "/merchants/{merchant_id}/collection-pricing-rules",
    response_model=APIResponse[list[CollectionPricingRuleResponse]],
)
def list_merchant_collection_pricing_rules(
    merchant_id: uuid.UUID,
    _admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
):
    client = get_supabase_admin()
    if not get_by_id(client, "merchants", merchant_id):
        raise NotFoundError("Merchant not found")
    rows = _list_rules(client, merchant_id=merchant_id)
    return APIResponse(data=[CollectionPricingRuleResponse(**row) for row in rows])


@router.post(
    "/merchants/{merchant_id}/collection-pricing-rules",
    response_model=APIResponse[CollectionPricingRuleResponse],
)
def create_merchant_collection_pricing_rule(
    merchant_id: uuid.UUID,
    payload: CollectionPricingRuleCreate,
    admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
    _rate_limit: Annotated[None, _WRITE_RATE_LIMIT],
):
    client = get_supabase_admin()
    if not get_by_id(client, "merchants", merchant_id):
        raise NotFoundError("Merchant not found")

    row = insert_row(
        client,
        _TABLE,
        {"merchant_id": str(merchant_id), "created_by": str(admin.id), **_create_rule_fields(payload)},
    )
    write_audit_log(
        client,
        actor_id=admin.id,
        merchant_id=merchant_id,
        action="collection_pricing_rule.created",
        resource_type="merchant_collection_pricing_rule",
        resource_id=uuid.UUID(row["id"]),
        metadata={"percentage_fee": str(row["percentage_fee"]), "channel": row.get("channel")},
    )
    return APIResponse(data=CollectionPricingRuleResponse(**row))


@router.patch("/collection-pricing-rules/{pricing_rule_id}", response_model=APIResponse[CollectionPricingRuleResponse])
def update_collection_pricing_rule(
    pricing_rule_id: uuid.UUID,
    payload: CollectionPricingRuleUpdate,
    admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
    _rate_limit: Annotated[None, _WRITE_RATE_LIMIT],
):
    client = get_supabase_admin()
    existing = get_by_id(client, _TABLE, pricing_rule_id)
    if not existing:
        raise NotFoundError("Collection pricing rule not found")

    fields = _rule_fields(payload, exclude_unset=True)
    if fields:
        row = update_row(client, _TABLE, pricing_rule_id, fields) or existing
        write_audit_log(
            client,
            actor_id=admin.id,
            merchant_id=uuid.UUID(existing["merchant_id"]) if existing.get("merchant_id") else None,
            action="collection_pricing_rule.updated",
            resource_type="merchant_collection_pricing_rule",
            resource_id=pricing_rule_id,
            metadata={"fields": sorted(fields.keys())},
        )
    else:
        row = existing
    return APIResponse(data=CollectionPricingRuleResponse(**row))


@router.post(
    "/collection-pricing-rules/{pricing_rule_id}/deactivate",
    response_model=APIResponse[CollectionPricingRuleResponse],
)
def deactivate_collection_pricing_rule(
    pricing_rule_id: uuid.UUID,
    admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
    _rate_limit: Annotated[None, _WRITE_RATE_LIMIT],
):
    client = get_supabase_admin()
    existing = get_by_id(client, _TABLE, pricing_rule_id)
    if not existing:
        raise NotFoundError("Collection pricing rule not found")

    row = update_row(client, _TABLE, pricing_rule_id, {"is_active": False})
    write_audit_log(
        client,
        actor_id=admin.id,
        merchant_id=uuid.UUID(existing["merchant_id"]) if existing.get("merchant_id") else None,
        action="collection_pricing_rule.deactivated",
        resource_type="merchant_collection_pricing_rule",
        resource_id=pricing_rule_id,
    )
    return APIResponse(data=CollectionPricingRuleResponse(**row))


@router.post(
    "/collection-pricing-rules/{pricing_rule_id}/activate",
    response_model=APIResponse[CollectionPricingRuleResponse],
)
def activate_collection_pricing_rule(
    pricing_rule_id: uuid.UUID,
    admin: Annotated[AuthenticatedUser, Depends(require_super_admin)],
    _rate_limit: Annotated[None, _WRITE_RATE_LIMIT],
):
    client = get_supabase_admin()
    existing = get_by_id(client, _TABLE, pricing_rule_id)
    if not existing:
        raise NotFoundError("Collection pricing rule not found")

    row = update_row(client, _TABLE, pricing_rule_id, {"is_active": True})
    write_audit_log(
        client,
        actor_id=admin.id,
        merchant_id=uuid.UUID(existing["merchant_id"]) if existing.get("merchant_id") else None,
        action="collection_pricing_rule.activated",
        resource_type="merchant_collection_pricing_rule",
        resource_id=pricing_rule_id,
    )
    return APIResponse(data=CollectionPricingRuleResponse(**row))


def _rule_fields(
    payload: CollectionPricingRuleCreate | CollectionPricingRuleUpdate, *, exclude_unset: bool = False
) -> dict:
    return payload.model_dump(mode="json", exclude_unset=exclude_unset)


def _create_rule_fields(payload: CollectionPricingRuleCreate) -> dict:
    """Like _rule_fields, but never sends an explicit null for
    effective_from — the column is NOT NULL DEFAULT now() in Postgres;
    omitting it (rather than nulling it out) lets that default apply,
    same as admin_pricing.py's identical helper."""
    fields = _rule_fields(payload)
    if fields.get("effective_from") is None:
        fields["effective_from"] = utc_now_iso()
    return fields
