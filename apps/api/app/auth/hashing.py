"""Hashing for merchant API keys.

Only the hash is ever stored (see api_keys.hashed_key) — the plaintext key
is shown to the merchant once, at creation time, and never persisted.
"""

import hashlib


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
