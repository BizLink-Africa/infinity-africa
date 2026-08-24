"""Super Admin "Customers" — GET /v1/admin/customers.

There is no populated customers table to read from: public.customers
exists in the schema but is never written to by any real code path (a
collection's customer_id is only ever set if a caller explicitly passes
one, which none of the real collection-creation flows do) — it would
show zero rows if queried directly. What genuinely exists, for every
real payment, is `collections.customer_phone` (always present) and,
where the collection is payment-link-bound, `payment_links.customer_name`
(often present). "Customers" here is derived by grouping real collections
by (merchant_id, customer_phone) — matching the page's own description,
"everyone who has actually paid a merchant" — rather than reading an
empty table.

Aggregation happens in Python, not SQL, since supabase-py's query
builder has no GROUP BY. Fine at this platform's current real scale
(a handful of merchants, a small number of collections); the
_MAX_COLLECTIONS_SCANNED cap below is the honest boundary of that
approach — a real materialized view/RPC would be needed if collection
volume grows far beyond it, not attempted here.
"""

import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from supabase import Client

from app.core.pagination import PaginationParams
from app.services.admin_directory import batch_merchant_names

_MAX_COLLECTIONS_SCANNED = 5000


@dataclass
class _CustomerAgg:
    merchant_id: str
    phone: str
    full_name: str | None = None
    currency: str = "TZS"
    total_spent: Decimal = field(default_factory=lambda: Decimal(0))
    transaction_count: int = 0
    first_seen_at: str | None = None
    last_transaction_at: str | None = None


def _earliest(a: str | None, b: str) -> str:
    return b if a is None or b < a else a


def _latest(a: str | None, b: str) -> str:
    return b if a is None or b > a else a


def list_admin_customers(
    client: Client, *, merchant_id: uuid.UUID | None, pagination: PaginationParams
) -> tuple[list[dict], int]:
    query = (
        client.table("collections")
        .select("merchant_id,customer_phone,payment_link_id,amount,currency,status,completed_at,created_at")
        .order("created_at", desc=True)
        .limit(_MAX_COLLECTIONS_SCANNED)
    )
    if merchant_id is not None:
        query = query.eq("merchant_id", str(merchant_id))
    collections = (query.execute()).data or []
    collections = [c for c in collections if c.get("customer_phone")]

    payment_link_ids = {c["payment_link_id"] for c in collections if c.get("payment_link_id")}
    names_by_payment_link_id: dict[str, str] = {}
    if payment_link_ids:
        links = (
            client.table("payment_links")
            .select("id,customer_name")
            .in_("id", list(payment_link_ids))
            .execute()
        ).data or []
        names_by_payment_link_id = {link["id"]: link["customer_name"] for link in links if link.get("customer_name")}

    groups: dict[tuple[str, str], _CustomerAgg] = {}
    for row in collections:
        key = (row["merchant_id"], row["customer_phone"])
        agg = groups.setdefault(key, _CustomerAgg(merchant_id=row["merchant_id"], phone=row["customer_phone"]))

        name = names_by_payment_link_id.get(row.get("payment_link_id"))
        if name and not agg.full_name:
            agg.full_name = name

        agg.currency = row.get("currency") or agg.currency
        agg.transaction_count += 1
        if row["status"] == "successful":
            agg.total_spent += Decimal(str(row["amount"]))

        activity_at = row.get("completed_at") or row["created_at"]
        agg.first_seen_at = _earliest(agg.first_seen_at, row["created_at"])
        agg.last_transaction_at = _latest(agg.last_transaction_at, activity_at)

    ordered = sorted(groups.values(), key=lambda a: a.last_transaction_at or "", reverse=True)
    total = len(ordered)
    page = ordered[pagination.start : pagination.end + 1]

    merchant_ids = {a.merchant_id for a in page}
    merchant_names = batch_merchant_names(client, merchant_ids)

    data = [
        {
            "id": f"{a.merchant_id}:{a.phone}",
            "merchant_id": a.merchant_id,
            "merchant_name": merchant_names.get(a.merchant_id, ""),
            "full_name": a.full_name,
            "phone": a.phone,
            "currency": a.currency,
            "total_spent": a.total_spent,
            "transaction_count": a.transaction_count,
            "first_seen_at": a.first_seen_at,
            "last_transaction_at": a.last_transaction_at,
        }
        for a in page
    ]
    return data, total
