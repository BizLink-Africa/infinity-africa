"""Response handling for the Selcom Checkout/Collections API
(https://developers.selcommobile.com/).

**Most endpoint response bodies are still unconfirmed.** Create Order -
Minimal, wallet-payment, and get-order-status are the exceptions —
their real sample responses (below) were recovered from the docs
directly and, for create-order-minimal, confirmed against a real
production call (2026-08-22, order reference S20690427372).
get-order-status's exact field names (data[0].order_id/creation_date/
amount/payment_status/transid/channel/reference/phone) came from the
webhook/reconciliation task brief, not independently re-verified against
a live call the way create-order-minimal was — treat the *shape*
(data as a list, per every other confirmed Checkout response) as solid,
but confirm the exact field names against the first real response this
codebase actually receives before fully trusting them. Every other
Checkout endpoint (process-card-payment, etc.) still has no confirmed
response shape at all. Per this task's own instruction not to guess,
don't add field extraction for those until a real example confirms the
actual field names. app/services/selcom/parsing.py guessed field names
for this same product before a real reference was available and was
wrong in several ways once real ones surfaced elsewhere in this
codebase (see app/services/selcom_business/parsing.py's docstring for
that history) — this module exists specifically so that mistake isn't
repeated here.

What IS always safe to implement without guessing: decoding the raw HTTP
envelope (status code, JSON-or-not) — every JSON API does this the same
way regardless of Selcom-specific field names.
"""

import base64
import binascii
import json
import logging

from app.services.selcom_checkout.errors import SelcomCheckoutError
from app.services.selcom_checkout.schemas import (
    CreateOrderMinimalResult,
    OrderStatusResult,
    SelcomPesaPaymentResult,
    SelcomPesaPaymentStatus,
    WalletPaymentResult,
    WalletPaymentStatus,
)

logger = logging.getLogger("infinity.selcom_checkout")


def decode_json_response(*, status_code: int, body: bytes, path: str) -> dict:
    """Raises SelcomCheckoutError for a non-2xx status or an unparseable
    body; otherwise returns the decoded JSON as-is, unparsed further — see
    module docstring for why field-level extraction isn't implemented
    yet."""
    if status_code >= 400:
        raise SelcomCheckoutError(
            f"Selcom Checkout API returned HTTP {status_code} for {path}",
            provider_status_code=status_code,
        )
    try:
        return json.loads(body) if body else {}
    except ValueError as exc:
        raise SelcomCheckoutError(f"Selcom Checkout API returned a non-JSON response for {path}") from exc


def base64_encode_url(url: str) -> str:
    """Per the docs: "All URLs in the request and response are base64
    encoded" — used for redirect_url/cancel_url/webhook on the way out.
    Never applied to non-URL fields (buyer_email, buyer_name, etc.)."""
    return base64.b64encode(url.encode("utf-8")).decode("ascii")


def base64_decode_url(value: str) -> str:
    """The inverse, for payment_gateway_url on the way in. Falls back to
    the raw value on a decode failure rather than raising — the order was
    still genuinely created on Selcom's side at that point (this runs
    after a successful response), so losing that record over a decode
    hiccup would be worse than surfacing a possibly-still-encoded string.
    Logs a warning either way so this doesn't fail silently."""
    try:
        decoded = base64.b64decode(value, validate=True).decode("utf-8")
        logger.info("selcom_checkout_url_decoded")
        return decoded
    except (binascii.Error, UnicodeDecodeError, ValueError):
        logger.warning("selcom_checkout_url_decode_failed")
        return value


# --- Create Order - Minimal ---------------------------------------------------------
#
# Confirmed sample response (https://developers.selcommobile.com/#create-order-minimal):
#
#     {"reference": "0289999288", "resultcode": "000", "result": "SUCCESS",
#      "message": "Payment notification logged",
#      "data": [{"gateway_buyer_uuid": "12344321", "payment_token": "80008000",
#                 "qr": "QR", "payment_gateway_url": "aHR0cDpleGFtcGxlLmNvbS9wZy90MTIyMjI="}]}
#
# Note `data` is a *list* containing one object, not a bare object — easy
# to get wrong (every other Selcom response shape seen in this codebase so
# far has `data` as a dict, see selcom_business/parsing.py).


def parse_create_order_minimal_response(response: dict) -> CreateOrderMinimalResult:
    data_list = response.get("data")
    data = data_list[0] if isinstance(data_list, list) and data_list else {}
    if not isinstance(data, dict):
        data = {}

    raw_payment_gateway_url = data.get("payment_gateway_url")
    payment_gateway_url = base64_decode_url(raw_payment_gateway_url) if raw_payment_gateway_url else None

    return CreateOrderMinimalResult(
        reference=str(response.get("reference") or ""),
        resultcode=str(response.get("resultcode") or ""),
        result=str(response.get("result") or ""),
        message=str(response.get("message") or ""),
        gateway_buyer_uuid=data.get("gateway_buyer_uuid"),
        payment_token=data.get("payment_token"),
        qr=data.get("qr"),
        payment_gateway_url=payment_gateway_url,
        raw_response=response,
    )


# --- wallet-payment ------------------------------------------------------------------
#
# Confirmed sample response (task brief, matching this endpoint's normal
# PENDING outcome — Selcom resolves the actual push result asynchronously,
# via callback, not in this response):
#
#     {"reference": "0289999288", "resultcode": "111", "result": "PENDING",
#      "message": "Request in progress. You will receive a callback shortly.",
#      "data": []}
#
# Status mapping, per task instruction:
#   000 / result == "SUCCESS"        -> "successful"
#   111 or 927                       -> "processing" (the *normal* case, not a failure)
#   999                               -> "ambiguous"
#   anything else                     -> "failed"


def _map_wallet_payment_status(*, resultcode: str, result: str) -> WalletPaymentStatus:
    if resultcode == "000" or result.upper() == "SUCCESS":
        return "successful"
    if resultcode in ("111", "927"):
        return "processing"
    if resultcode == "999":
        return "ambiguous"
    return "failed"


def parse_wallet_payment_response(response: dict) -> WalletPaymentResult:
    resultcode = str(response.get("resultcode") or "")
    result = str(response.get("result") or "")

    return WalletPaymentResult(
        reference=str(response.get("reference") or ""),
        resultcode=resultcode,
        result=result,
        message=str(response.get("message") or ""),
        status=_map_wallet_payment_status(resultcode=resultcode, result=result),
        raw_response=response,
    )


# --- selcompesa-payment ---------------------------------------------------------------
#
# No confirmed sample response of its own — treated as the same envelope
# shape as wallet-payment (same product family, same documented pattern
# of every Checkout endpoint sharing {reference, resultcode, result,
# message, data}), pending confirmation against a real sandbox call via
# scripts/test_selcom_checkout_selcompesa_payment.py. Same status mapping
# as wallet-payment, for the same reason (Selcom resolves the actual push
# result asynchronously for every push-style endpoint in this product).


def _map_selcompesa_payment_status(*, resultcode: str, result: str) -> SelcomPesaPaymentStatus:
    return _map_wallet_payment_status(resultcode=resultcode, result=result)


def parse_selcompesa_payment_response(response: dict) -> SelcomPesaPaymentResult:
    resultcode = str(response.get("resultcode") or "")
    result = str(response.get("result") or "")

    return SelcomPesaPaymentResult(
        reference=str(response.get("reference") or ""),
        resultcode=resultcode,
        result=result,
        message=str(response.get("message") or ""),
        status=_map_selcompesa_payment_status(resultcode=resultcode, result=result),
        raw_response=response,
    )


# --- get-order-status ------------------------------------------------------------
#
# data as a list (per every other confirmed Checkout response shape) with
# fields per the reconciliation task brief: order_id, creation_date,
# amount, payment_status, transid, channel, reference, phone. Field
# *names* here are less battle-tested than create-order-minimal's — see
# module docstring.


def parse_order_status_response(response: dict) -> OrderStatusResult:
    data_list = response.get("data")
    data = data_list[0] if isinstance(data_list, list) and data_list else {}
    if not isinstance(data, dict):
        data = {}

    # Both a top-level `reference` and a per-order `data[0].reference` are
    # documented for this endpoint — prefer the more specific per-order
    # one when present, matching the docs' own field list.
    reference = str(data.get("reference") or response.get("reference") or "")

    return OrderStatusResult(
        reference=reference,
        resultcode=str(response.get("resultcode") or ""),
        result=str(response.get("result") or ""),
        message=str(response.get("message") or ""),
        order_id=data.get("order_id"),
        creation_date=data.get("creation_date"),
        amount=str(data["amount"]) if data.get("amount") is not None else None,
        payment_status=data.get("payment_status"),
        transid=data.get("transid"),
        channel=data.get("channel"),
        phone=data.get("phone") or data.get("msisdn"),
        raw_response=response,
    )
