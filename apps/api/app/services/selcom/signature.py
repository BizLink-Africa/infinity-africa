"""Outbound request signing for calls this backend makes *to* Selcom.

The mirror image of app/services/selcom/webhooks.py, which verifies the
HMAC-SHA256 signature Selcom attaches to *inbound* webhook deliveries — same
primitive (HMAC-SHA256 over the exact raw request body, hex-digested),
applied in the outbound direction.

**Not verified against Selcom's live API reference.** No Selcom API
documentation was available in the session that wrote this — the header
names, digest scheme, and "Authorization: SELCOM <key>" shape below follow
the common pattern Selcom's public integration guides describe elsewhere,
but must be checked against Selcom's current, real API reference (and
tested against a real sandbox account) before SELCOM_MODE=live is ever used
against production. See docs/selcom-live-go-live.md.
"""

import hashlib
import hmac
from datetime import datetime, timezone


def build_timestamp() -> str:
    """ISO 8601 UTC, second precision — the format most signature schemes
    of this shape expect. Adjust here if Selcom's real docs specify
    otherwise; every caller goes through this one function."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_digest(payload: bytes, *, api_secret: str) -> str:
    """HMAC-SHA256 of the exact raw request body, hex-digested — the same
    primitive selcom_webhooks.py's compute_selcom_signature() uses for the
    inbound direction."""
    return hmac.new(api_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def sign_request(
    payload: bytes,
    *,
    api_key: str,
    api_secret: str,
    vendor_id: str,
    timestamp: str | None = None,
) -> dict[str, str]:
    """Returns the headers to attach to an outbound Selcom API call.
    api_secret never appears in the return value — only its HMAC digest
    does, matching this codebase's "log/transmit safe metadata only, never
    the secret itself" convention."""
    ts = timestamp or build_timestamp()
    digest = compute_digest(payload, api_secret=api_secret)
    return {
        "Authorization": f"SELCOM {api_key}",
        "Digest-Method": "HS256",
        "Digest": digest,
        "Timestamp": ts,
        "Vendor": vendor_id,
        "Content-Type": "application/json",
    }
