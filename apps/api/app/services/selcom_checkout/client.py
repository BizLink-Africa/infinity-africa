"""The Selcom Checkout/Collections API client
(https://developers.selcommobile.com/).

create_order_minimal() below is the first endpoint method implemented —
Step 1 for STK/USSD/wallet push, payment-link checkout, and dynamic
QR/token display. It creates an order shell on Selcom's side and returns
a payment_token/qr/gateway URL; it never itself pulls money (no
wallet-payment call happens here or anywhere in this module yet).

Every other endpoint method (get-order-status, process-wallet-payment,
etc.) still needs three things confirmed first, none of them guessed:

1. The exact request field names and their required order (that order
   becomes both the signing string and the Signed-Fields header).
2. The exact response field names.
3. A real sandbox round-trip proving both.

SelcomCheckoutHTTPClient._signed_request below is the one place every
endpoint method calls through — it handles signing, sending, and
envelope decoding generically; only the per-endpoint path/fields change
per call. Confirmed endpoint paths, for when more of these are added
(https://developers.selcommobile.com/, fetched 2026-08-22):

    POST /v1/checkout/create-order
    POST /v1/checkout/create-order-minimal   (implemented — see below)
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
from app.services.selcom_checkout.parsing import (
    base64_encode_url,
    decode_json_response,
    parse_create_order_minimal_response,
)
from app.services.selcom_checkout.schemas import (
    CreateOrderMinimalResult,
    SelcomCheckoutCredentials,
)
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

    async def _signed_request(
        self, method: str, path: str, fields: dict[str, str], *, timestamp: str | None = None
    ) -> dict:
        """`fields` must be given in the exact order Selcom's docs specify
        for this endpoint — that order becomes both the signing string and
        the Signed-Fields header, and is sent as the JSON body verbatim
        (POST-shaped calls only; a GET/query-parameter endpoint needs its
        own handling once implemented, not guessed here). Never logs
        `fields` (may contain customer phone numbers/amounts) or any
        credential — only path/status/latency, matching the convention
        already established in app/services/selcom_business/live_client.py.

        `timestamp` defaults to signer.build_timestamp()'s UTC ISO-8601
        shape (via build_auth_headers) — the override exists only so
        scripts/test_selcom_checkout_sandbox.py can test the docs'
        alternative "yyyy-dd-mm H:i:s" format against a real sandbox
        without touching this production default. Never set this from
        application code."""
        credentials = self._credentials
        headers = build_auth_headers(
            fields,
            api_key=credentials.api_key,
            digest_method=credentials.digest_method,
            api_secret=credentials.api_secret,
            private_key_base64=credentials.private_key_base64,
            timestamp=timestamp,
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

    async def create_order_minimal(
        self,
        *,
        order_id: str,
        buyer_email: str,
        buyer_name: str,
        buyer_phone: str,
        amount: str,
        no_of_items: int,
        currency: str = "TZS",
        buyer_remarks: str | None = None,
        merchant_remarks: str | None = None,
        redirect_url: str | None = None,
        cancel_url: str | None = None,
        webhook: str | None = None,
        timestamp: str | None = None,
    ) -> CreateOrderMinimalResult:
        """POST /v1/checkout/create-order-minimal
        (https://developers.selcommobile.com/#create-order-minimal) —
        creates an order shell for non-card payments; never itself pulls
        money (this method never calls a wallet-payment endpoint, and
        neither does anything else in this module yet).

        Field order below is deliberate, not incidental — it becomes both
        the signing string and the Signed-Fields header, and the docs
        require both to match the payload exactly. The docs' own shell
        example lists a *different* Signed-Fields set for this endpoint
        (buyer_user_id, payment_methods, payer_remarks, order_items) that
        doesn't match any example payload shown for Create Order -
        Minimal (those fields belong to a different Checkout endpoint's
        docs, most likely the full Create Order, not Minimal). Once
        fields not present in any Minimal example are dropped, the
        shell's order and the parameter-table order below turn out
        identical for every field this method actually sends — so field
        *order* isn't the open question here. What's still unconfirmed is
        the Timestamp *format*: the shell headers describe
        "yyyy-dd-mm H:i:s", not the ISO-8601 signer.build_timestamp()
        produces by default — see the `timestamp` param below and
        scripts/test_selcom_checkout_sandbox.py, which tries both against
        a real sandbox.

        buyer_phone must already be normalized to "255XXXXXXXXX" by the
        caller (app.core.phone.normalize_tz_phone) — not re-validated
        here, since this client has no phone-format opinion of its own.

        redirect_url/cancel_url/webhook are base64-encoded here per the
        docs ("All URLs in the request and response are base64
        encoded") — never encode buyer_email/buyer_name/remarks/etc.

        `timestamp` overrides the default ISO-8601 UTC timestamp — never
        set this from application code, it exists only for the sandbox
        diagnostic script above.
        """
        fields: dict[str, str] = {
            "vendor": self._credentials.vendor,
            "order_id": order_id,
            "buyer_email": buyer_email,
            "buyer_name": buyer_name,
            "buyer_phone": buyer_phone,
            "amount": amount,
            "currency": currency,
        }
        if redirect_url:
            fields["redirect_url"] = base64_encode_url(redirect_url)
        if cancel_url:
            fields["cancel_url"] = base64_encode_url(cancel_url)
        if webhook:
            fields["webhook"] = base64_encode_url(webhook)
        if buyer_remarks:
            fields["buyer_remarks"] = buyer_remarks
        if merchant_remarks:
            fields["merchant_remarks"] = merchant_remarks
        fields["no_of_items"] = str(no_of_items)

        response = await self._signed_request(
            "POST", "/v1/checkout/create-order-minimal", fields, timestamp=timestamp
        )
        return parse_create_order_minimal_response(response)
