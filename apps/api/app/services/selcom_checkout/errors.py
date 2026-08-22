"""Selcom Checkout/Collections API error types
(https://developers.selcommobile.com/).

Distinct from app.services.selcom_business's errors (a different Selcom
product, its own RSA-only signing scheme, developer.selcom.business) and
from app/services/selcom/ (the older, explicitly-unverified placeholder
for this same checkout/collections product — see
docs/selcom-live-go-live.md for why that one was never taken live). This
module supersedes app/services/selcom/ once endpoint methods are added;
until then both exist side by side.
"""

from fastapi import status

from app.core.errors import SelcomAPIError


class SelcomCheckoutError(SelcomAPIError):
    """Selcom Checkout API returned a non-2xx response, an unparseable
    body, or the request failed outright (timeout/connection error).
    Inherits provider_status_code/is_ip_whitelist_error/
    provider_response_body from the shared base."""


class SelcomCheckoutMisconfiguredError(SelcomCheckoutError):
    """A required credential/setting is missing or invalid before any
    request was even sent — e.g. no SELCOM_CHECKOUT_API_SECRET configured
    while SELCOM_CHECKOUT_DIGEST_METHOD=HS256, or an unsupported digest
    method value. Distinguished from a real Selcom API failure (which
    means a request was actually sent and Selcom responded)."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "selcom_checkout_misconfigured"
