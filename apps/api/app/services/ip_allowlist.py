"""Merchant-configured IP allowlist enforcement — only ever applies to
`live`-environment API traffic (see app/auth/dependencies.py::verify_api_key).
An empty/no-active-rows allowlist is NOT a lockout: enforcement is opt-in,
triggered only once a merchant has at least one `active` row for that
environment, matching the task brief's "if IP allowlist is enabled for a
production key" — there's no separate on/off switch, having an active row
*is* "enabled".
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


def is_ip_allowed(client: Client, *, merchant_id: uuid.UUID, environment: str, ip: str | None) -> bool:
    """True if this request should proceed. Sandbox is never restricted —
    callers should only call this for `environment == "live"`."""
    active_rows = (
        client.table("api_ip_allowlist")
        .select("ip_address_or_cidr")
        .eq("merchant_id", str(merchant_id))
        .eq("environment", environment)
        .eq("status", "active")
        .execute()
    ).data or []

    if not active_rows:
        return True  # no active allowlist configured -> unrestricted

    if not ip:
        return False  # allowlist is active but we couldn't determine the caller's IP -> fail closed

    return any(_matches(ip, row["ip_address_or_cidr"]) for row in active_rows)
