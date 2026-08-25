"""Generates the human-friendly Merchant ID (see
supabase/migrations/20260829010000_merchants_merchant_code.sql): an 8-digit
code, always starting with 27, e.g. 27048391. For identification/search only
— never an authentication secret, never used as or inside an API key.

Random rather than sequential (a counter would leak the platform's total
merchant count to anyone who can see two Merchant IDs) — uses `secrets`,
Python's cryptographically safe RNG, not `random`.
"""

import secrets

from supabase import Client

from app.core.errors import MerchantCodeGenerationError

_PREFIX = "27"
_SUFFIX_DIGITS = 6
_MAX_ATTEMPTS = 20


def _candidate() -> str:
    suffix = secrets.randbelow(10**_SUFFIX_DIGITS)
    return f"{_PREFIX}{suffix:0{_SUFFIX_DIGITS}d}"


def _code_exists(client: Client, code: str) -> bool:
    result = client.table("merchants").select("id").eq("merchant_code", code).execute()
    return bool(result.data)


def generate_merchant_code(client: Client) -> str:
    """Generates a random, unique 27****** Merchant ID, checking the
    database for a collision on each attempt (the unique index on
    merchants.merchant_code is the atomic backstop against a concurrent
    race between the check here and the insert the caller does right
    after — this loop just keeps ordinary collisions rare in practice).

    Raises MerchantCodeGenerationError if _MAX_ATTEMPTS candidates all
    collide — fails loudly rather than ever silently reusing or truncating
    an ID."""
    for _ in range(_MAX_ATTEMPTS):
        candidate = _candidate()
        if not _code_exists(client, candidate):
            return candidate
    raise MerchantCodeGenerationError(
        f"Could not generate a unique Merchant ID after {_MAX_ATTEMPTS} attempts"
    )
