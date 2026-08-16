"""Shared payment_links logic used by app.routers.payment_links,
app.routers.invoices (which generates a "Pay Now" payment_links row for an
invoice), and app.routers.collections (which needs to validate a
payment_link_id passed into a collection-initiation request the same way).
"""

import secrets
import uuid
from datetime import datetime, timezone

from supabase import Client

from app.config import get_settings
from app.core.errors import ConflictError, ValidationAPIError
from app.schemas.enums import CollectionMethod
from app.services.crud import get_by_id, update_row


def generate_public_slug() -> str:
    # 16 random bytes (128 bits) url-safe-encoded — "generate a secure
    # public payment URL": unguessable, and distinct from the row's own id.
    return secrets.token_urlsafe(16)


def build_public_url(public_slug: str) -> str:
    settings = get_settings()
    return f"{settings.public_app_url}/pay/{public_slug}"


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def get_with_effective_status(client: Client, payment_link_id: uuid.UUID) -> dict | None:
    """Fetches a payment_links row and applies the same lazy-expiry rule as
    everywhere else: nothing sweeps expires_at on a timer, so if the stored
    status is still ACTIVE but expires_at has passed, this promotes it to
    EXPIRED and persists that before returning."""
    link = get_by_id(client, "payment_links", payment_link_id)
    if not link:
        return None
    return with_effective_status(client, link)


def with_effective_status(client: Client, link: dict) -> dict:
    if link["status"] == "ACTIVE":
        expires_at = link.get("expires_at")
        if expires_at and _parse_dt(expires_at) <= datetime.now(timezone.utc):
            updated = update_row(client, "payment_links", uuid.UUID(link["id"]), {"status": "EXPIRED"})
            if updated:
                link = updated
    return link


def batch_collection_counts(client: Client, payment_link_ids: set[str]) -> dict[str, int]:
    """How many collection attempts (collections.payment_link_id) exist per
    link — used for the merchant-portal list/detail view's "attempt_count".
    Same batch-then-aggregate-in-Python shape as
    app/services/admin_directory.py::batch_merchant_names, since neither the
    real Supabase REST client usage here nor the in-memory test fake do
    server-side GROUP BY."""
    if not payment_link_ids:
        return {}
    rows = (
        client.table("collections")
        .select("payment_link_id")
        .in_("payment_link_id", list(payment_link_ids))
        .execute()
    ).data or []
    counts: dict[str, int] = {}
    for row in rows:
        link_id = row["payment_link_id"]
        counts[link_id] = counts.get(link_id, 0) + 1
    return counts


async def validate_payment_link_for_collection(
    client: Client, *, merchant_id: uuid.UUID, payment_link_id: uuid.UUID | None, method: CollectionMethod
) -> None:
    """When payment_link_id is provided on a collection-initiation request:
    it must belong to the caller's own merchant, be currently payable
    (ACTIVE — applying the same lazy-expiry rule as everywhere else), and
    accept this specific method. Shared by both the flat /v1/collections/*
    router and the self-service /v1/merchant/collections/* router — the
    self-service router previously skipped this check entirely."""
    if payment_link_id is None:
        return

    link = get_with_effective_status(client, payment_link_id)
    if not link or uuid.UUID(link["merchant_id"]) != merchant_id:
        raise ValidationAPIError("payment_link_id does not belong to this merchant")
    if link["status"] != "ACTIVE":
        raise ConflictError(f"This payment link cannot accept a collection (status: {link['status']})")
    if method.value not in link["allowed_payment_methods"]:
        raise ValidationAPIError(f"{method.value} is not an accepted method for this payment link")
