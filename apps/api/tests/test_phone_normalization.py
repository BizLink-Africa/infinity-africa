"""app/core/phone.py — the single shared Tanzanian phone normalization
implementation every schema/validator and every Selcom-bound payload goes
through.
"""

import pytest

from app.core.phone import (
    InvalidPhoneNumberError,
    normalize_tz_phone,
    validate_and_normalize_phone,
)


@pytest.mark.parametrize(
    "raw",
    [
        "+255747730270",
        "255747730270",
        "0747730270",
        "747730270",
        "+255 747 730 270",
        "0747 730 270",
    ],
)
def test_normalizes_every_accepted_input_shape(raw):
    assert normalize_tz_phone(raw) == "255747730270"


def test_zero_prefixed_six_series_number():
    assert normalize_tz_phone("0657730270") == "255657730270"


def test_bare_six_series_nine_digit_number():
    assert normalize_tz_phone("657730270") == "255657730270"


def test_dashes_and_brackets_are_stripped():
    assert normalize_tz_phone("(0747) 730-270") == "255747730270"


def test_never_returns_a_plus_sign():
    result = normalize_tz_phone("+255747730270")
    assert "+" not in result


@pytest.mark.parametrize(
    "raw",
    [
        "12345",  # too short
        "2557477302700",  # too long (13 digits)
        "855747730270",  # wrong country code (12 digits, doesn't start with 255)
        "8747730270",  # 10 digits but doesn't start with 0
        "abc7477302700",  # non-digits
        "",
    ],
)
def test_rejects_invalid_phone_numbers(raw):
    with pytest.raises(InvalidPhoneNumberError):
        normalize_tz_phone(raw)


def test_validate_and_normalize_phone_raises_plain_value_error():
    with pytest.raises(ValueError):
        validate_and_normalize_phone("not-a-phone")

    assert validate_and_normalize_phone("0747730270") == "255747730270"
