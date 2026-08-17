r"""Tanzanian phone number normalization — the single shared implementation
every schema/validator and every Selcom-bound payload must go through.
Before this module, four separate files each defined their own loose
`\+?[0-9]{9,15}` pattern and none of them normalized to a single canonical
shape, so the exact same number could be stored as "+255700000000",
"255700000000", or "0700000000" depending on which endpoint received it —
and none of those are what Selcom's Business API expects (a bare
"255XXXXXXXXX", never a "+").

Every phone number this backend stores or sends to Selcom must go through
normalize_tz_phone() (directly, or via validate_and_normalize_phone() from
a Pydantic field_validator) so there is exactly one canonical
representation everywhere.
"""

import re

_STRIP_CHARS = re.compile(r"[\s\-()]")

_ERROR_MESSAGE = (
    "must be a valid Tanzanian phone number "
    "(e.g. 255747730270, 0747730270, or 747730270)"
)


class InvalidPhoneNumberError(ValueError):
    pass


def normalize_tz_phone(raw: str) -> str:
    """Normalizes any of the accepted input shapes to the one canonical
    form Selcom's Business API requires: "255XXXXXXXXX", digits only, never
    a leading "+".

    Accepted inputs (spaces/dashes/brackets/plus are stripped first):
      - 0XXXXXXXXX   (10 digits, leading 0)      -> 255XXXXXXXXX
      - 7XXXXXXXX / 6XXXXXXXX (9 digits)          -> 255XXXXXXXXX
      - 255XXXXXXXXX (12 digits, already correct) -> unchanged

    Raises InvalidPhoneNumberError for anything else (wrong length, wrong
    leading digit, non-digit characters left after stripping).
    """
    digits = _STRIP_CHARS.sub("", raw).replace("+", "")

    if not digits.isdigit():
        raise InvalidPhoneNumberError(_ERROR_MESSAGE)

    if len(digits) == 10 and digits.startswith("0"):
        return "255" + digits[1:]

    if len(digits) == 9 and digits[0] in ("6", "7"):
        return "255" + digits

    if len(digits) == 12 and digits.startswith("255"):
        return digits

    raise InvalidPhoneNumberError(_ERROR_MESSAGE)


def validate_and_normalize_phone(value: str) -> str:
    """Pydantic-`field_validator`-friendly wrapper — raises a plain
    `ValueError` (Pydantic wraps this into its own validation error shape)
    rather than the InvalidPhoneNumberError subclass, so it drops straight
    into an existing `@field_validator`/`@model_validator` call site."""
    try:
        return normalize_tz_phone(value)
    except InvalidPhoneNumberError as exc:
        raise ValueError(str(exc)) from exc
