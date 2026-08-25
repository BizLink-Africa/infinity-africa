"""Merchant-configured IP allowlist enforcement — only ever applies to
`live`-environment API traffic (see app/auth/dependencies.py::verify_api_key).

Business decision (amended 2026-08-26): IP whitelisting is an explicit
per-key choice the merchant makes at creation time
(api_keys.ip_whitelist_enabled), not an implicit "having any active row
turns it on" inference. A key with ip_whitelist_enabled=false — the default,
"continue without IP whitelisting" — accepts a valid key from any IP even if
the merchant happens to have allowlist rows configured (e.g. for another
key).

Amended again 2026-08-27: an allowlist row now optionally scopes to one
specific key (api_ip_allowlist.api_key_id) — the inline "Allowed server
IPs" list added at key-creation time always sets it. A row with
api_key_id=null is merchant+environment-wide (the original standalone IP
Allowlist page behavior) and still matches every key in that environment
that has whitelisting enabled. Enforcement for a given key therefore
matches active rows where api_key_id is null OR equals that key's id.
"""

import ipaddress
import uuid

from supabase import Client


def _matches(ip: str, entry: str) -> bool:
    try:
        candidate = ipaddress.ip_address(ip)
    except ValueError:
        return False
    try:
        if "/" in entry:
            return candidate in ipaddress.ip_network(entry, strict=False)
        return candidate == ipaddress.ip_address(entry)
    except ValueError:
        return False


def is_ip_allowed(
    client: Client,
    *,
    merchant_id: uuid.UUID,
    api_key_id: uuid.UUID,
    environment: str,
    ip: str | None,
    ip_whitelist_enabled: bool,
) -> bool:
    """True if this request should proceed. Sandbox is never restricted —
    callers should only call this for `environment == "live"`."""
    if not ip_whitelist_enabled:
        return True  # merchant chose "continue without IP whitelisting" for this key

    all_active_rows = (
        client.table("api_ip_allowlist")
        .select("ip_address_or_cidr, api_key_id")
        .eq("merchant_id", str(merchant_id))
        .eq("environment", environment)
        .eq("status", "active")
        .execute()
    ).data or []
    key_id_str = str(api_key_id)
    active_rows = [row for row in all_active_rows if row.get("api_key_id") in (None, key_id_str)]

    if not ip:
        return False  # allowlist is enabled but we couldn't determine the caller's IP -> fail closed

    if not active_rows:
        return False  # enabled, but no IP has been approved yet -> fail closed, not open

    return any(_matches(ip, row["ip_address_or_cidr"]) for row in active_rows)
