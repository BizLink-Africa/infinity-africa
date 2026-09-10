"""Tanzania NIDA (National Identification Number) handling — the single
shared implementation every onboarding path goes through.

A NIDA number is 20 digits, commonly written grouped as
``YYYYMMDD-NNNNN-NNNNN-NN`` (8-5-5-2) with dashes and/or spaces. We accept
any grouping and store digits only.

Rules (see docs/PRE_TRAFFIC_SECURITY_CHECK.md and the task brief):
  * required — a blank value raises NidaRequiredError
  * validated for a reasonable Tanzanian shape — exactly 20 digits
  * stored digits-only, never logged in full
  * only ever surfaced to the Super Admin UI masked (last 4 digits)
"""

import re

from app.core.errors import NidaInvalidError, NidaRequiredError

_NON_DIGIT = re.compile(r"\D")

# Tanzania NIDA is 20 digits. Kept as a named constant so a future format
# change (or a second accepted length) is a one-line edit.
NIDA_DIGIT_LENGTH = 20


def normalize_nida(raw: str | None) -> str:
    """Return the NIDA number as exactly ``NIDA_DIGIT_LENGTH`` digits, no
    separators. Raises NidaRequiredError for an empty value and
    NidaInvalidError for anything that isn't the right number of digits."""
    if raw is None or not raw.strip():
        raise NidaRequiredError("NIDA number is required.")

    digits = _NON_DIGIT.sub("", raw)

    if not digits:
        raise NidaRequiredError("NIDA number is required.")

    if len(digits) != NIDA_DIGIT_LENGTH:
        raise NidaInvalidError(
            f"Enter a valid NIDA number — it should be {NIDA_DIGIT_LENGTH} digits."
        )

    return digits


def mask_nida(value: str | None) -> str | None:
    """Last 4 digits only, for display in the Super Admin review UI —
    e.g. ``••••••••••••••••1234``. Returns None if there's nothing to mask."""
    if not value:
        return None
    digits = _NON_DIGIT.sub("", value)
    if not digits:
        return None
    last4 = digits[-4:]
    return "•" * max(len(digits) - 4, 0) + last4


def nida_last4(value: str | None) -> str | None:
    """Just the last 4 digits (or None) — the API response only ever
    exposes this, never the full number."""
    if not value:
        return None
    digits = _NON_DIGIT.sub("", value)
    return digits[-4:] if digits else None
