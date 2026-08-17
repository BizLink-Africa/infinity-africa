"""RSA-SHA256 request signing for the Selcom Business Disbursement API
(https://developer.selcom.business/).

Confirmed scheme (fetched directly from that page — not a guess, but also
not a verified sandbox round-trip, since no real credentials were
available in this environment):

    signing_string = "timestamp=" + timestamp + "&field1=value1&field2=value2..."
    digest          = Base64(RSA-SHA256(signing_string, private_key))
    signed-fields   = comma-separated field names, in the exact order signed
    timestamp       = UTC ISO-8601 with milliseconds, e.g. 2026-05-27T06:01:03.273Z

Distinct from app/services/selcom/signature.py — that's HMAC-SHA256 for a
different Selcom product (the checkout/collections API) and is untouched
by this module.
"""

import base64
from datetime import datetime, timezone

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey


def build_timestamp() -> str:
    now = datetime.now(timezone.utc)
    milliseconds = now.microsecond // 1000
    return f"{now.strftime('%Y-%m-%dT%H:%M:%S')}.{milliseconds:03d}Z"


def _build_signing_string(*, timestamp: str, fields: dict[str, str]) -> str:
    parts = [f"timestamp={timestamp}"]
    parts.extend(f"{key}={value}" for key, value in fields.items())
    return "&".join(parts)


def _load_private_key(private_key_base64: str) -> RSAPrivateKey:
    if not private_key_base64:
        raise ValueError("SELCOM_BUSINESS_PRIVATE_KEY_BASE64 is not configured")
    pem_bytes = base64.b64decode(private_key_base64)
    key = serialization.load_pem_private_key(pem_bytes, password=None)
    if not isinstance(key, RSAPrivateKey):
        raise TypeError("SELCOM_BUSINESS_PRIVATE_KEY_BASE64 must decode to an RSA private key")
    return key


def sign_request(
    fields: dict[str, str], *, private_key_base64: str, timestamp: str | None = None
) -> tuple[str, str, str]:
    """Returns (timestamp, digest, signed_fields_header) for the
    `timestamp`/`digest`/`signed-fields` headers — `api-key` is added by
    the caller directly, it isn't part of the signature. `fields` must be
    given in the exact order they should be signed (and therefore the
    exact order `signed-fields` lists them in) — a plain dict preserves
    insertion order, so callers just build it in the right order."""
    ts = timestamp or build_timestamp()
    signing_string = _build_signing_string(timestamp=ts, fields=fields)
    private_key = _load_private_key(private_key_base64)
    signature = private_key.sign(signing_string.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    digest = base64.b64encode(signature).decode("ascii")
    signed_fields = ",".join(fields.keys())
    return ts, digest, signed_fields
