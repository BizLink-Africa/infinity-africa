"""Reversible encryption for the one kind of secret this codebase must be
able to recover after creation: a webhook signing secret, needed in full
every time an outbound delivery is HMAC-signed (app.services.webhooks.
sign_outbound_payload). Never use this for API key secrets — those are
show-once and hash-only by design (app.auth.hashing.hash_api_key), and must
stay that way even if it would be more convenient not to.

Backed by Fernet (AES-128-CBC + HMAC, from the `cryptography` package
already a dependency for Selcom's RSA signing) — an authenticated symmetric
cipher, not just obfuscation. The key comes from
settings.webhook_secret_encryption_key (Railway/production env var only,
never committed) or, when blank, is deterministically derived from the
Supabase service role key so local dev/test never needs a separate secret to
be productive. That fallback is explicitly insecure for a real deployment
(anyone with the already-sensitive service role key could derive it) — set
WEBHOOK_SECRET_ENCRYPTION_KEY for real before any merchant relies on it.
"""

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    settings = get_settings()
    raw_key = settings.webhook_secret_encryption_key
    if raw_key:
        key = raw_key.encode("utf-8")
    else:
        seed = (settings.supabase_service_role_key or "insecure-dev-only-fallback").encode("utf-8")
        key = base64.urlsafe_b64encode(hashlib.sha256(seed).digest())
    return Fernet(key)


def encrypt_secret(raw: str) -> str:
    return _fernet().encrypt(raw.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str) -> str | None:
    """None (not a raised error) for a token that can't be decrypted under
    the current key — e.g. a stale value from before a key rotation. Callers
    treat that the same as "no secret configured" rather than crashing a
    webhook send."""
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None
