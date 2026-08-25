"""Batch-lookup helpers shared by the /v1/admin/* list endpoints
(app/routers/admin.py) — joining a merchant_name or a person's display name
onto rows from tables that don't store them directly.

No table stores a person's full name; only Supabase Auth's
user_metadata.full_name does. best_effort_user_profile/batch_user_profiles
resolve it via the service-role client's Auth admin API, deliberately
swallowing any failure (user deleted, network hiccup, malformed metadata)
and returning None rather than failing the whole list — a missing name is
a cosmetic gap, not a reason to break a dashboard page.
"""

import uuid

from supabase import Client


def batch_merchant_names(client: Client, merchant_ids: set[str]) -> dict[str, str]:
    if not merchant_ids:
        return {}
    rows = (
        client.table("merchants").select("id, business_name").in_("id", list(merchant_ids)).execute()
    ).data or []
    return {row["id"]: row["business_name"] for row in rows}


def batch_merchant_codes(client: Client, merchant_ids: set[str]) -> dict[str, str]:
    """id -> merchant_code (the human-friendly 27****** Merchant ID), for
    join-on-display on every Super Admin page that lists merchant-owned
    rows — same shape/usage as batch_merchant_names, kept as its own
    function (not merged into it) so every existing `.get(id, "")` caller
    of batch_merchant_names is unaffected."""
    if not merchant_ids:
        return {}
    rows = (
        client.table("merchants").select("id, merchant_code").in_("id", list(merchant_ids)).execute()
    ).data or []
    return {row["id"]: row["merchant_code"] for row in rows}


def batch_api_key_prefixes(client: Client, api_key_ids: set[str]) -> dict[str, str]:
    """id -> key_prefix, for join-on-display only — never selects hashed_key."""
    if not api_key_ids:
        return {}
    rows = (
        client.table("api_keys").select("id, key_prefix").in_("id", list(api_key_ids)).execute()
    ).data or []
    return {row["id"]: row["key_prefix"] for row in rows}


def best_effort_user_profile(client: Client, user_id: str | uuid.UUID | None) -> dict:
    if not user_id:
        return {"full_name": None, "email": None}
    try:
        result = client.auth.admin.get_user_by_id(str(user_id))
        user = result.user
        full_name = (user.user_metadata or {}).get("full_name") if user.user_metadata else None
        return {"full_name": full_name, "email": user.email}
    except Exception:  # noqa: BLE001 - deliberately broad: a deleted user, a
        # network hiccup, or malformed metadata should all degrade to "no
        # name" rather than break the enclosing admin list request.
        return {"full_name": None, "email": None}


def batch_user_profiles(client: Client, user_ids: set[str]) -> dict[str, dict]:
    return {user_id: best_effort_user_profile(client, user_id) for user_id in user_ids}
