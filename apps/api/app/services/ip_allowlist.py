"""Merchant-configured IP allowlist enforcement — only ever applies to
`live`-environment API traffic (see app/auth/dependencies.py::verify_api_key).

Business decision (amended 2026-08-26): IP whitelisting is an explicit
per-key choice the merchant makes at creation time
(api_keys.ip_whitelist_enabled), not an implicit "having any active row
turns it on" inference. A key with ip_whitelist_enabled=false — the default,
"continue without IP whitelisting" — accepts a valid key from any IP even if
the merchant happens to have allowlist rows configured (e.g. for another
key).
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
    environment: str,
    ip: str | None,
    ip_whitelist_enabled: bool,
) -> bool:
    """True if this request should proceed. Sandbox is never restricted —
    callers should only call this for `environment == "live"`."""
    if not ip_whitelist_enabled:
        return True  # merchant chose "continue without IP whitelisting" for this key

    active_rows = (
        client.table("api_ip_allowlist")
        .select("ip_address_or_cidr")
        .eq("merchant_id", str(merchant_id))
        .eq("environment", environment)
        .eq("status", "active")
        .execute()
    ).data or []

    if not ip:
        return False  # allowlist is enabled but we couldn't determine the caller's IP -> fail closed

    if not active_rows:
        return False  # enabled, but no IP has been approved yet -> fail closed, not open

    return any(_matches(ip, row["ip_address_or_cidr"]) for row in active_rows)
