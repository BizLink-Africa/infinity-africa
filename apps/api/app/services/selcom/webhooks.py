"""Mock Selcom webhook signature verification.

No live Selcom integration exists yet (see mock_client.py), so there's no
real signature scheme to match either. This stands in for one: HMAC-SHA256
over the exact raw request body, using a shared secret
(settings.selcom_webhook_secret) — the same shape a real provider signature
header typically takes. compute_selcom_signature is the inverse, used by
tests (and anything simulating an inbound Selcom delivery) to build a
validly-signed request.
"""

import hashlib
import hmac


def compute_selcom_signature(*, raw_body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


def verify_selcom_signature(*, raw_body: bytes, signature: str | None, secret: str) -> bool:
    if not signature or not secret:
        return False
    expected = compute_selcom_signature(raw_body=raw_body, secret=secret)
    return hmac.compare_digest(expected, signature)
