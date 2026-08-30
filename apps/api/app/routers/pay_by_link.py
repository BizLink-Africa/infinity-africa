"""Pay by Link — a merchant's permanent public checkout page
(/pay/{slug}), additive to (never replacing) the existing generated/
shareable payment links in app/routers/payment_links.py. See
docs/PAY_BY_LINK.md for the full design and
app/services/pay_by_link.py for the slug/checkout logic this router only
ever delegates to.

Two routers, same split as payment_links.py:
  router         — /merchant/pay-by-link, JWT-authenticated, own-merchant-only
  public_router  — /public/pay-by-link, unauthenticated

Super Admin visibility (GET /v1/admin/merchants/{id}/pay-by-link) lives
in app/routers/admin.py instead, next to that router's existing
merchant-scoped GET endpoints (.../api-keys, ...) — not a third router
here.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, status

from app.auth import require_own_merchant_role
from app.core.errors import APIError, ConflictError, NotFoundError
from app.core.feature_flags import require_collections_enabled
from app.core.rate_limit import rate_limit
from app.database.session import get_supabase_admin
from app.schemas.auth import MerchantMembership
from app.schemas.common import APIResponse
from app.schemas.enums import UserRole
from app.schemas.pay_by_link import (
    PayByLinkCheckoutRequest,
    PayByLinkCheckoutResponse,
    PayByLinkCreate,
    PayByLinkResponse,
    PayByLinkUpdate,
    PublicPayByLinkResponse,
)
from app.services.audit import write_audit_log
from app.services.crud import execute_maybe_single, insert_row, update_row
from app.services.idempotency import run_idempotent
from app.services.pay_by_link import (
    check_slug_available,
    ensure_merchant_accepts_payments,
    execute_pay_by_link_checkout,
    generate_default_slug,
    get_own_pay_link,
)
from app.services.payment_links import build_public_url

router = APIRouter(prefix="/merchant/pay-by-link", tags=["pay-by-link"])
public_router = APIRouter(prefix="/public/pay-by-link", tags=["pay-by-link (public)"])

_ADMIN_AND_STAFF = (UserRole.MERCHANT_ADMIN, UserRole.MERCHANT_STAFF)


def _to_response(row: dict) -> PayByLinkResponse:
    return PayByLinkResponse(**row, public_url=build_public_url(row["slug"]))


# --- Merchant Portal (JWT-authenticated) -------------------------------------


@router.get("/me", response_model=APIResponse[PayByLinkResponse | None])
def get_my_pay_by_link(
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role())],
):
    """Null (not 404) when the merchant hasn't created their permanent
    page yet — the frontend uses this to show "Create your Pay by Link"
    rather than treating an unset page as an error."""
    client = get_supabase_admin()
    row = get_own_pay_link(client, merchant_id=membership.merchant_id)
    return APIResponse(data=_to_response(row) if row else None)


@router.get("/slug-availability", response_model=APIResponse[dict])
def check_my_pay_by_link_slug_availability(
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
    _rate_limit: Annotated[None, Depends(rate_limit(scope="pay_by_link_slug_check", limit=30, window_seconds=60))],
    slug: Annotated[str, Query(min_length=1, max_length=60)],
):
    """Lets the merchant portal show "This slug is already taken." live,
    before the merchant even submits the create/edit form — doesn't
    reserve anything, purely informational (the real check happens again,
    authoritatively, at create/update time)."""
    client = get_supabase_admin()
    existing = get_own_pay_link(client, merchant_id=membership.merchant_id)
    normalized = slug.strip().lower()
    try:
        check_slug_available(
            client, normalized, exclude_pay_link_id=uuid.UUID(existing["id"]) if existing else None
        )
        return APIResponse(data={"available": True})
    except APIError as exc:
        # A bad/taken slug is an expected, common outcome of a live
        # availability check — reported as data (available: False), not
        # a 4xx, so the frontend doesn't need a try/catch just to render
        # "This slug is already taken." while the merchant is still
        # typing.
        return APIResponse(data={"available": False, "reason": exc.message})


@router.post("", response_model=APIResponse[PayByLinkResponse], status_code=status.HTTP_201_CREATED)
def create_my_pay_by_link(
    payload: PayByLinkCreate,
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
    _rate_limit: Annotated[None, Depends(rate_limit(scope="pay_by_link_manage", limit=10, window_seconds=60))],
):
    client = get_supabase_admin()

    if get_own_pay_link(client, merchant_id=membership.merchant_id):
        raise ConflictError("This merchant already has a Pay by Link page. Edit it instead of creating another.")

    merchant = ensure_merchant_accepts_payments(client, merchant_id=membership.merchant_id)

    display_name = payload.display_name or merchant["business_name"]
    slug = payload.slug
    if slug:
        check_slug_available(client, slug)
    else:
        slug = generate_default_slug(client, merchant["business_name"])

    row = insert_row(
        client,
        "merchant_pay_links",
        {
            "merchant_id": str(membership.merchant_id),
            "slug": slug,
            "display_name": display_name,
            "description": payload.description,
            "is_active": True,
            "last_used_at": None,
            "created_by": str(membership.user_id),
        },
    )

    write_audit_log(
        client,
        actor_id=membership.user_id,
        merchant_id=membership.merchant_id,
        action="pay_by_link.created",
        resource_type="merchant_pay_link",
        resource_id=uuid.UUID(row["id"]),
        metadata={"slug": slug},
    )

    return APIResponse(data=_to_response(row))


@router.patch("/me", response_model=APIResponse[PayByLinkResponse])
def update_my_pay_by_link(
    payload: PayByLinkUpdate,
    membership: Annotated[MerchantMembership, Depends(require_own_merchant_role(*_ADMIN_AND_STAFF))],
    _rate_limit: Annotated[None, Depends(rate_limit(scope="pay_by_link_manage", limit=10, window_seconds=60))],
):
    client = get_supabase_admin()
    existing = get_own_pay_link(client, merchant_id=membership.merchant_id)
    if not existing:
        raise NotFoundError("Pay by Link page not found")

    updates: dict = {}
    if payload.display_name is not None:
        updates["display_name"] = payload.display_name
    if payload.description is not None:
        updates["description"] = payload.description
    if payload.slug is not None and payload.slug != existing["slug"]:
        check_slug_available(client, payload.slug, exclude_pay_link_id=uuid.UUID(existing["id"]))
        updates["slug"] = payload.slug
    if payload.is_active is not None:
        updates["is_active"] = payload.is_active

    row = existing
    if updates:
        row = update_row(client, "merchant_pay_links", uuid.UUID(existing["id"]), updates) or existing

        action = (
            "pay_by_link.enabled"
            if updates.get("is_active") is True
            else "pay_by_link.disabled"
            if updates.get("is_active") is False
            else "pay_by_link.updated"
        )
        write_audit_log(
            client,
            actor_id=membership.user_id,
            merchant_id=membership.merchant_id,
            action=action,
            resource_type="merchant_pay_link",
            resource_id=uuid.UUID(existing["id"]),
            metadata={"fields": sorted(updates.keys())},
        )

    return APIResponse(data=_to_response(row))


# --- Public (unauthenticated) — "public customers can access only a
# safe view of an active page" is enforced right here. ----------------------


@public_router.get("/{slug}", response_model=APIResponse[PublicPayByLinkResponse])
def get_public_pay_by_link(slug: str):
    client = get_supabase_admin()
    row = execute_maybe_single(
        client.table("merchant_pay_links").select("*").eq("slug", slug.strip().lower()).maybe_single()
    )
    if not row:
        raise NotFoundError("Pay by Link page not found")

    return APIResponse(
        data=PublicPayByLinkResponse(
            display_name=row["display_name"], description=row.get("description"), is_active=row["is_active"]
        )
    )


@public_router.post(
    "/{slug}/checkout",
    response_model=APIResponse[PayByLinkCheckoutResponse],
    status_code=status.HTTP_201_CREATED,
)
async def checkout_pay_by_link(
    slug: str,
    payload: PayByLinkCheckoutRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    _rate_limit: Annotated[None, Depends(rate_limit(scope="pay_by_link_checkout", limit=20, window_seconds=60))],
):
    """Looks up the merchant purely from `slug` — merchant_id is never
    accepted from the request body (feature brief Part 6/11: "Merchant ID
    must come from the slug lookup on backend", "Do not trust frontend
    merchant_id"). Creates a fresh payment_links row and returns its
    public checkout URL; the frontend does a full-page redirect there —
    see app/services/pay_by_link.py::execute_pay_by_link_checkout for why
    no collection/wallet/ledger logic lives here at all.

    Idempotency-Key-guarded like every other money-adjacent public POST
    in this codebase (collect_payment_link, pay_payment_link, ...) — a
    retried/double-clicked submission must reuse the same payment_links
    row rather than mint a second one for the same customer intent."""
    require_collections_enabled()
    client = get_supabase_admin()

    pay_link = execute_maybe_single(
        client.table("merchant_pay_links").select("*").eq("slug", slug.strip().lower()).maybe_single()
    )
    if not pay_link:
        raise NotFoundError("Pay by Link page not found")

    merchant_id = uuid.UUID(pay_link["merchant_id"])

    async def _handler() -> tuple[int, dict]:
        # Checked inside the handler, not before run_idempotent, so a
        # retry of an already-succeeded request replays the stored
        # response rather than failing on a state the first request
        # itself may have caused — same convention as
        # payment_links.py::collect_payment_link.
        if not pay_link["is_active"]:
            raise ConflictError("This Pay by Link page is currently disabled.")
        ensure_merchant_accepts_payments(client, merchant_id=merchant_id)

        result = await execute_pay_by_link_checkout(
            client,
            pay_link=pay_link,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            phone=payload.phone,
            amount=payload.amount,
            currency=payload.currency,
            description=payload.description,
        )

        # Public/customer-initiated, not an authenticated actor —
        # actor_type "system" matches the convention used everywhere
        # else in this codebase for an action nobody logged in
        # triggered directly (e.g. resolve_collection's own audit
        # entries). Never logs the customer's name/email/phone (feature
        # brief Part 13: "Do not log sensitive customer data
        # unnecessarily") — only the amount/currency and which
        # payment_links row resulted, same shape as every other money-
        # adjacent audit entry in this codebase.
        write_audit_log(
            client,
            actor_type="system",
            merchant_id=merchant_id,
            action="pay_by_link.payment_initiated",
            resource_type="payment_link",
            resource_id=uuid.UUID(result["payment_link"]["id"]),
            metadata={"amount": str(payload.amount), "currency": payload.currency, "slug": slug},
        )

        body = {"payment_link_id": result["payment_link"]["id"], "redirect_url": result["public_url"]}
        return status.HTTP_201_CREATED, body

    _status_code, body = await run_idempotent(
        client,
        merchant_id=merchant_id,
        endpoint="POST /public/pay-by-link/{slug}/checkout",
        idempotency_key=idempotency_key,
        request_payload={"slug": slug, **payload.model_dump(mode="json")},
        handler=_handler,
    )

    return APIResponse(data=PayByLinkCheckoutResponse(**body))
