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
