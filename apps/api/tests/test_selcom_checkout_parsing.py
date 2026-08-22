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
