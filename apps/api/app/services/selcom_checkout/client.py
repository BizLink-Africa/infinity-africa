"""The Selcom Checkout/Collections API client foundation
(https://developers.selcommobile.com/).

Auth/signing foundation only, at this stage. No endpoint methods
(create-order, get-order-status, process-wallet-payment, etc.) are
implemented yet — this task covers the signing/header layer every future
endpoint call will share. Adding an endpoint method safely needs three
things confirmed first, none of them guessed here:

1. The exact request field names and their required order (that order
   becomes both the signing string and the Signed-Fields header).
2. The exact response field names (not available from the docs fetched
   for this task — see parsing.py).
3. A real sandbox round-trip proving both.

SelcomCheckoutHTTPClient._signed_request below is the one place every
future endpoint method will call through — it handles signing, sending,
and envelope decoding generically; only the per-endpoint path/fields
change per call. Confirmed endpoint paths, for when that work starts
(https://developers.selcommobile.com/, fetched 2026-08-22):

    POST /v1/checkout/create-order
    POST /v1/checkout/create-order-minimal
    POST /v1/checkout/cancel-order
    GET  /v1/checkout/get-order-status
    GET  /v1/checkout/list-orders
    GET  /v1/checkout/fetch-card-tokens
    POST /v1/checkout/delete-card
    POST /v1/checkout/process-card-payment
    POST /v1/checkout/process-wallet-payment
    POST /v1/checkout/process-selcom-pesa-payment
    POST /v1/checkout/create-till-alias
    POST /v1/checkout/webhook-callback   (inbound — handled in a router, not this client)

USSD Push / STK Push / Dynamic QR were not documented on the fetched
page (only a wallet-cashin-flavored "Push USSD" for C2B collection was
shown) — confirm these with Selcom support before assuming they exist
under these or similar paths.
"""

import logging
import time

import httpx

from app.config import Settings, get_settings
from app.services.selcom_checkout.errors import (
    SelcomCheckoutError,
    SelcomCheckoutMisconfiguredError,
)
from app.services.selcom_checkout.parsing import decode_json_response
from app.services.selcom_checkout.schemas import SelcomCheckoutCredentials
from app.services.selcom_checkout.signer import build_auth_headers

logger = logging.getLogger("infinity.selcom_checkout")


def get_selcom_checkout_credentials(settings: Settings | None = None) -> SelcomCheckoutCredentials:
    """Builds credentials from Settings — the only place SELCOM_CHECKOUT_*
    env vars are read for this client. Returns them bundled in one object
    rather than as loose strings so nothing accidentally ends up in a log
    call's format string."""
    s = settings or get_settings()
    return SelcomCheckoutCredentials(
        base_url=s.selcom_checkout_base_url,
        api_key=s.selcom_checkout_api_key,
        api_secret=s.selcom_checkout_api_secret,
        digest_method=s.selcom_checkout_digest_method,
        vendor=s.selcom_checkout_vendor,
        private_key_base64=s.selcom_checkout_private_key_base64,
        timeout_seconds=s.selcom_checkout_timeout_seconds,
    )


class SelcomCheckoutHTTPClient:
    """Raw signed HTTP calls to Selcom's Checkout API. No endpoint-specific
    methods yet — see module docstring for why, and for the confirmed
    path list ready for when that work starts."""

    def __init__(self, *, credentials: SelcomCheckoutCredentials):
        if not credentials.base_url:
            raise SelcomCheckoutMisconfiguredError("SELCOM_CHECKOUT_BASE_URL is not configured")
        if not credentials.api_key:
            raise SelcomCheckoutMisconfiguredError("SELCOM_CHECKOUT_API_KEY is not configured")
        self._credentials = credentials

    async def _signed_request(self, method: str, path: str, fields: dict[str, str]) -> dict:
        """`fields` must be given in the exact order Selcom's docs specify
        for this endpoint — that order becomes both the signing string and
        the Signed-Fields header, and is sent as the JSON body verbatim
        (POST-shaped calls only; a GET/query-parameter endpoint needs its
        own handling once implemented, not guessed here). Never logs
        `fields` (may contain customer phone numbers/amounts) or any
        credential — only path/status/latency, matching the convention
        already established in app/services/selcom_business/live_client.py."""
        credentials = self._credentials
        headers = build_auth_headers(
            fields,
            api_key=credentials.api_key,
            digest_method=credentials.digest_method,
            api_secret=credentials.api_secret,
            private_key_base64=credentials.private_key_base64,
        )
        if credentials.vendor:
            headers["Vendor"] = credentials.vendor

        url = f"{credentials.base_url.rstrip('/')}{path}"
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=credentials.timeout_seconds) as http:
                response = await http.request(method, url, json=fields, headers=headers)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPError) as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            logger.warning(
                "selcom_checkout_request_failed path=%s latency_ms=%d error=%s",
                path,
                latency_ms,
                type(exc).__name__,
            )
            raise SelcomCheckoutError(f"Could not reach Selcom Checkout ({type(exc).__name__})") from exc

        latency_ms = int((time.monotonic() - started) * 1000)
        logger.info(
            "selcom_checkout_request path=%s status=%d latency_ms=%d", path, response.status_code, latency_ms
        )
        return decode_json_response(status_code=response.status_code, body=response.content, path=path)
