"""Selcom Checkout/Collections API request signing
(https://developers.selcommobile.com/).

Confirmed directly from that page (fetched 2026-08-22 — not guessed):

    Authorization:  "SELCOM " + Base64(api_key)
    Digest-Method:  "HS256" or "RS256"
    Digest:         Base64(HMAC-SHA256(signing_string, api_secret))   for HS256
                     Base64(RSA-SHA256(signing_string, private_key))   for RS256
    Timestamp:      ISO 8601, e.g. "2019-02-26T09:30:46+03:00"
    Signed-Fields:  comma-separated field names, in the exact order signed
                     (timestamp is never itself listed here, even though
                     it's always first in the signing string)

Quoting the docs directly: "Construct a string in this exact format:
timestamp=<timestamp>&field1=value1&field2=value2&...". Rules stated
alongside that: timestamp is always first, even when it isn't itself a
signed field; the remaining fields follow Signed-Fields order exactly;
no extra spaces; values must match the request payload exactly. The
docs present HS256 and RS256 as two supported options without saying
which applies to which account — Selcom support confirms this per
account (see docs/selcom-checkout-go-live.md once written).

Distinct from:
- app/services/selcom/signature.py — an *unconfirmed* HMAC scheme
  written for the same product family before this real reference was
  available. Do not reuse; this module supersedes it.
- app/services/selcom_business/signing.py — the Business Disbursement
  API's RSA-SHA256 signer (developer.selcom.business, a different Selcom
  product with its own header names: lowercase `api-key`/`timestamp`/
  `digest`/`signed-fields`, no `Authorization`/`Digest-Method` split).
  Same general `timestamp=...&field=value...` shape, different headers.

Timestamp format: UTC, millisecond precision, "Z" suffix — the same
scheme already proven against real Selcom production traffic in
selcom_business/signing.py — rather than the doc's own example offset
(+03:00, Tanzania local time). Both are valid ISO-8601 instants; this
specific product's tolerance for UTC vs. local-offset timestamps is
unconfirmed until tested against a real sandbox call.
"""

import base64
import hashlib
import hmac
from datetime import datetime, timezone

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from app.services.selcom_checkout.errors import SelcomCheckoutMisconfiguredError

_SUPPORTED_DIGEST_METHODS = ("HS256", "RS256")


def build_timestamp() -> str:
    now = datetime.now(timezone.utc)
    milliseconds = now.microsecond // 1000
    return f"{now.strftime('%Y-%m-%dT%H:%M:%S')}.{milliseconds:03d}Z"


def build_timestamp_php_style() -> str:
    """The literal alternative format the Create Order - Minimal shell
    sample's headers describe: "Timestamp: {timestamp in yyyy-dd-mm H:i:s
    format}" — year, then *day*, then month (not the more common
    year-month-day), followed by 24-hour time, no timezone suffix. Not
    ISO-8601, and untested against a real Selcom response as of writing.

    **Never called from client.py's default path.** Exists only for
    scripts/test_selcom_checkout_sandbox.py to test against a real
    sandbox alongside build_timestamp()'s UTC ISO-8601 default — see that
    script and create_order_minimal()'s docstring for why both are worth
    trying rather than guessing which one Selcom's server actually
    expects."""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%d-%m %H:%M:%S")


def build_signing_string(*, timestamp: str, fields: dict[str, str]) -> str:
    """`fields` must be given in the exact order they should be signed —
    a plain dict preserves insertion order, so callers just build it in
    the right order (that same order becomes Signed-Fields). Timestamp is
    always first, per the docs, even though it's never itself included in
    Signed-Fields."""
    parts = [f"timestamp={timestamp}"]
    parts.extend(f"{key}={value}" for key, value in fields.items())
    return "&".join(parts)


def _sign_hmac(signing_string: str, *, api_secret: str) -> str:
    if not api_secret:
        raise SelcomCheckoutMisconfiguredError("SELCOM_CHECKOUT_API_SECRET is not configured")
    digest = hmac.new(api_secret.encode("utf-8"), signing_string.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def _load_private_key(private_key_base64: str) -> RSAPrivateKey:
    if not private_key_base64:
        raise SelcomCheckoutMisconfiguredError("SELCOM_CHECKOUT_PRIVATE_KEY_BASE64 is not configured")
    pem_bytes = base64.b64decode(private_key_base64)
    key = serialization.load_pem_private_key(pem_bytes, password=None)
    if not isinstance(key, RSAPrivateKey):
        raise SelcomCheckoutMisconfiguredError(
            "SELCOM_CHECKOUT_PRIVATE_KEY_BASE64 must decode to an RSA private key"
        )
    return key


def _sign_rsa(signing_string: str, *, private_key_base64: str) -> str:
    private_key = _load_private_key(private_key_base64)
    signature = private_key.sign(signing_string.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode("ascii")


def sign_request(
    fields: dict[str, str],
    *,
    digest_method: str,
    api_secret: str = "",
    private_key_base64: str = "",
    timestamp: str | None = None,
) -> tuple[str, str, str]:
    """Returns (timestamp, digest, signed_fields_header). `fields` must be
    given in the exact order they should be signed; `api_key` is not part
    of the signature (it goes straight into the Authorization header — see
    build_auth_headers). `digest_method` must be exactly "HS256" or
    "RS256" (case-sensitive, matching the Digest-Method header value)."""
    if digest_method not in _SUPPORTED_DIGEST_METHODS:
        raise SelcomCheckoutMisconfiguredError(
            f"Unsupported SELCOM_CHECKOUT_DIGEST_METHOD: {digest_method!r} (must be 'HS256' or 'RS256')"
        )

    ts = timestamp or build_timestamp()
    signing_string = build_signing_string(timestamp=ts, fields=fields)

    if digest_method == "HS256":
        digest = _sign_hmac(signing_string, api_secret=api_secret)
    else:
        digest = _sign_rsa(signing_string, private_key_base64=private_key_base64)

    signed_fields = ",".join(fields.keys())
    return ts, digest, signed_fields


def build_auth_headers(
    fields: dict[str, str],
    *,
    api_key: str,
    digest_method: str,
    api_secret: str = "",
    private_key_base64: str = "",
    timestamp: str | None = None,
) -> dict[str, str]:
    """Full header set for one signed Selcom Checkout request. Never logs
    or returns api_secret/private_key_base64 themselves — only the
    resulting digest, which isn't reversible back to the secret."""
    if not api_key:
        raise SelcomCheckoutMisconfiguredError("SELCOM_CHECKOUT_API_KEY is not configured")

    ts, digest, signed_fields = sign_request(
        fields,
        digest_method=digest_method,
        api_secret=api_secret,
        private_key_base64=private_key_base64,
        timestamp=timestamp,
    )
    authorization_key = base64.b64encode(api_key.encode("utf-8")).decode("ascii")
    return {
        "Authorization": f"SELCOM {authorization_key}",
        "Digest-Method": digest_method,
        "Digest": digest,
        "Timestamp": ts,
        "Signed-Fields": signed_fields,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
