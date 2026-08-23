"""app/services/selcom_checkout/parsing.py — Create Order - Minimal
response parsing against the real sample response recovered from
https://developers.selcommobile.com/#create-order-minimal (pasted into
this project 2026-08-22, not guessed):

    {"reference": "0289999288", "resultcode": "000", "result": "SUCCESS",
     "message": "Payment notification logged",
     "data": [{"gateway_buyer_uuid": "12344321", "payment_token": "80008000",
                "qr": "QR", "payment_gateway_url": "aHR0cDpleGFtcGxlLmNvbS9wZy90MTIyMjI="}]}

Note `data` is a *list* wrapping one object — different from every other
Selcom response shape seen in this codebase so far (selcom_business's is
a bare dict, see selcom_business/parsing.py).
"""

import base64

from app.services.selcom_checkout.parsing import (
    base64_decode_url,
    base64_encode_url,
    parse_create_order_minimal_response,
)

REAL_SAMPLE_RESPONSE = {
    "reference": "0289999288",
    "resultcode": "000",
    "result": "SUCCESS",
    "message": "Payment notification logged",
    "data": [
        {
            "gateway_buyer_uuid": "12344321",
            "payment_token": "80008000",
            "qr": "QR",
            "payment_gateway_url": "aHR0cDpleGFtcGxlLmNvbS9wZy90MTIyMjI=",
        }
    ],
}


def test_real_sample_response_parses_correctly():
    result = parse_create_order_minimal_response(REAL_SAMPLE_RESPONSE)

    assert result.reference == "0289999288"
    assert result.resultcode == "000"
    assert result.result == "SUCCESS"
    assert result.message == "Payment notification logged"
    assert result.gateway_buyer_uuid == "12344321"
    assert result.payment_token == "80008000"
    assert result.qr == "QR"
    assert result.is_success is True
    assert result.raw_response == REAL_SAMPLE_RESPONSE


def test_payment_gateway_url_is_decoded_from_base64():
    result = parse_create_order_minimal_response(REAL_SAMPLE_RESPONSE)

    # base64.b64decode("aHR0cDpleGFtcGxlLmNvbS9wZy90MTIyMjI=") == b"http:example.com/pg/t12222"
    assert result.payment_gateway_url == "http:example.com/pg/t12222"


def test_qr_is_not_base64_decoded():
    # The docs' own example uses the literal "QR" for this field — not a
    # base64 payload. base64_decode_url is never called on it, matching
    # the task's rule that `qr` itself is a response value, not a URL.
    result = parse_create_order_minimal_response(REAL_SAMPLE_RESPONSE)
    assert result.qr == "QR"


def test_missing_data_list_does_not_crash():
    response = {"reference": "REF-1", "resultcode": "651", "result": "FAIL", "message": "Invalid order"}
    result = parse_create_order_minimal_response(response)

    assert result.reference == "REF-1"
    assert result.is_success is False
    assert result.gateway_buyer_uuid is None
    assert result.payment_token is None
    assert result.qr is None
    assert result.payment_gateway_url is None


def test_empty_data_list_does_not_crash():
    response = {"reference": "REF-1", "resultcode": "651", "result": "FAIL", "message": "Invalid order", "data": []}
    result = parse_create_order_minimal_response(response)
    assert result.gateway_buyer_uuid is None


def test_is_success_false_for_a_non_success_result():
    response = {**REAL_SAMPLE_RESPONSE, "resultcode": "651", "result": "FAIL"}
    result = parse_create_order_minimal_response(response)
    assert result.is_success is False


# --- base64 URL helpers -------------------------------------------------------------


def test_base64_encode_url_round_trips_with_decode():
    url = "https://merchant.example.com/webhook/order-121212"
    encoded = base64_encode_url(url)

    assert encoded == base64.b64encode(url.encode("utf-8")).decode("ascii")
    assert base64_decode_url(encoded) == url


def test_base64_decode_url_falls_back_to_raw_value_on_bad_input():
    # Not valid base64 — must not raise, per the module's documented
    # "don't lose a genuinely-created order over a decode hiccup" rule.
    assert base64_decode_url("not-valid-base64!!!") == "not-valid-base64!!!"


def test_base64_decode_url_decodes_exactly_once_never_double_decoded():
    """Regression guard from the 2026-08-23 "Page Not Found" investigation
    — confirms decoding never runs twice even when the *decoded* value
    happens to itself look like valid base64 (a realistic risk: a real
    Selcom gateway token is a long opaque base64-looking string)."""
    # This decodes to another string that is itself valid base64 — if
    # base64_decode_url ever ran twice, this would silently mangle it.
    inner_looking_like_base64 = base64_encode_url("https://tza.selcom.online/paymentgw/checkout/abc123")
    doubly_encoded = base64_encode_url(inner_looking_like_base64)

    result = base64_decode_url(doubly_encoded)

    # One decode only — lands on the inner base64-looking string itself,
    # not the fully-unwrapped URL.
    assert result == inner_looking_like_base64
    assert result != "https://tza.selcom.online/paymentgw/checkout/abc123"


def test_base64_decode_url_does_not_truncate_a_realistic_long_token():
    """A real Selcom payment_gateway_url token is ~100+ characters —
    confirms the full length survives the round trip, matching the
    live-verified length (108 chars) from the 2026-08-23 diagnostic."""
    long_token = "S18B/PPffzQYqxlumcvgBGsNYCcX2SCc24esxMw3pJwDobXOGVZdY8566y1u7Vwm3duN70gAbboGNQ=="
    url = f"https://tza.selcom.online/paymentgw/checkout/{long_token}"
    encoded = base64_encode_url(url)

    decoded = base64_decode_url(encoded)

    assert decoded == url
    assert len(decoded) == len(url)
