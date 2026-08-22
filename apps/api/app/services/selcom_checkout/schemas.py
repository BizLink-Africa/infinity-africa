"""Pydantic models for the Selcom Checkout/Collections client foundation
(https://developers.selcommobile.com/).

No endpoint-specific request/response schemas yet — those need real,
confirmed field names per endpoint (Create Order, Get Order Status,
etc.), which the fetched documentation didn't include example payloads
for. See parsing.py's module docstring for what's confirmed vs. not.
This file currently only holds the credential bundle the signer/client
need.
"""

from pydantic import BaseModel


class SelcomCheckoutCredentials(BaseModel):
    """Everything signer.sign_request()/build_auth_headers() and
    client.SelcomCheckoutHTTPClient need, bundled so callers pass one
    object instead of six loose strings. Built from Settings by
    client.get_selcom_checkout_credentials() — construct directly with
    literal values only in tests."""

    base_url: str
    api_key: str
    api_secret: str = ""
    digest_method: str = "HS256"
    vendor: str = ""
    private_key_base64: str = ""
    timeout_seconds: int = 30


class CreateOrderMinimalResult(BaseModel):
    """Parsed result of POST /v1/checkout/create-order-minimal
    (https://developers.selcommobile.com/#create-order-minimal). Field
    names below match app.services.selcom_checkout.parsing's confirmed
    extraction — see that module for what's parsed vs. not.

    payment_gateway_url is the *decoded* URL, not the raw base64 Selcom
    returns (the docs: "All URLs in the request and response are base64
    encoded") — raw_response keeps the original, unmodified body for
    anyone who needs the exact bytes Selcom sent."""

    reference: str
    resultcode: str
    result: str
    message: str
    gateway_buyer_uuid: str | None = None
    payment_token: str | None = None
    qr: str | None = None
    payment_gateway_url: str | None = None
    raw_response: dict

    @property
    def is_success(self) -> bool:
        """Per the docs' own sample response
        ({"resultcode": "000", "result": "SUCCESS", ...}) — both checked
        since neither field's full value space is documented."""
        return self.resultcode == "000" or self.result == "SUCCESS"
