"""The live Selcom client — only ever constructed when SELCOM_MODE=live
(see app/services/selcom/client.py::get_selcom_client()).

**Placeholder pending Selcom's real API reference.** No Selcom API
documentation was available in the session that wrote this: endpoint paths,
signing headers, and response-field parsing below all follow a plausible,
industry-standard shape — not a confirmed one. Every path is a module-level
constant specifically so it's a one-line fix once the real reference is
available; nothing about the surrounding shape (signing, retries, error
handling, the PaymentProvider methods below) should need to change. See
app/services/selcom/signature.py's docstring for the same caveat on the
signing scheme, and docs/selcom-live-go-live.md for the full go-live
procedure — do not set SELCOM_MODE=live in production before working
through that document, in particular step 1 (fixing this file against
Selcom's real API reference) and step 2 (testing against a real sandbox).

Two things live here:
- SelcomHTTPClient: raw signed HTTP calls to Selcom's Collection/Payout API.
- LiveSelcomClient: the PaymentProvider implementation — translates this
  app's method-agnostic calls into the right SelcomHTTPClient call and
  parses the response back into CollectionResult/DynamicQrResult/
  DisbursementResult, the same shapes MockSelcomClient returns. Everything
  above this layer is written against that shared interface and never
  knows which client is active.
"""

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx

from app.core.errors import SelcomAPIError
from app.services.selcom.parsing import extract_provider_reference, extract_status
from app.services.selcom.schemas import (
    CollectionResult,
    DisbursementResult,
    DynamicQrResult,
)
from app.services.selcom.signature import sign_request
from app.services.selcom.withdrawals import initiate_withdrawal

logger = logging.getLogger("infinity.selcom")

_TIMEOUT_SECONDS = 15.0
_MAX_CONNECT_RETRIES = 1
_CLIENT_NAME = "selcom"

# Placeholder paths — see module docstring.
_PATH_USSD_PUSH = "/v1/checkout/push-ussd"
_PATH_STK_PUSH = "/v1/checkout/push-stk"
_PATH_SELCOM_PESA_PUSH = "/v1/checkout/push-wallet"
_PATH_DYNAMIC_QR = "/v1/checkout/qr"
_PATH_ORDER_STATUS = "/v1/checkout/order-status"
_PATH_PAYOUT = "/v1/payout/create"


class SelcomHTTPClient:
    def __init__(self, *, base_url: str, api_key: str, api_secret: str, vendor_id: str):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._api_secret = api_secret
        self._vendor_id = vendor_id

    async def _post(self, path: str, body: dict) -> dict:
        payload = json.dumps(body, default=str).encode("utf-8")
        headers = sign_request(payload, api_key=self._api_key, api_secret=self._api_secret, vendor_id=self._vendor_id)
        url = f"{self._base_url}{path}"

        attempt = 0
        while True:
            started = time.monotonic()
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as http:
                    response = await http.post(url, content=payload, headers=headers)
                break
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                latency_ms = int((time.monotonic() - started) * 1000)
                if attempt >= _MAX_CONNECT_RETRIES:
                    logger.warning(
                        "selcom_request_failed path=%s latency_ms=%d attempt=%d error=%s",
                        path, latency_ms, attempt, type(exc).__name__,
                    )
                    raise SelcomAPIError(f"Could not reach Selcom ({type(exc).__name__})") from exc
                attempt += 1
            except httpx.HTTPError as exc:
                latency_ms = int((time.monotonic() - started) * 1000)
                logger.warning(
                    "selcom_request_failed path=%s latency_ms=%d error=%s", path, latency_ms, type(exc).__name__
                )
                raise SelcomAPIError(f"Could not reach Selcom ({type(exc).__name__})") from exc

        latency_ms = int((time.monotonic() - started) * 1000)
        logger.info("selcom_request path=%s status=%d latency_ms=%d", path, response.status_code, latency_ms)

        if response.status_code >= 400:
            raise SelcomAPIError(f"Selcom returned HTTP {response.status_code} for {path}")

        try:
            return response.json()
        except ValueError as exc:
            raise SelcomAPIError(f"Selcom returned a non-JSON response for {path}") from exc

    async def _push(self, path: str, *, amount: Decimal, currency: str, customer_phone: str, reference: str) -> dict:
        return await self._post(
            path,
            {
                "vendor": self._vendor_id,
                "order_id": reference,
                "amount": str(amount),
                "currency": currency,
                "msisdn": customer_phone,
            },
        )

    async def push_ussd(self, *, amount: Decimal, currency: str, customer_phone: str, reference: str) -> dict:
        return await self._push(_PATH_USSD_PUSH, amount=amount, currency=currency, customer_phone=customer_phone, reference=reference)

    async def push_stk(self, *, amount: Decimal, currency: str, customer_phone: str, reference: str) -> dict:
        return await self._push(_PATH_STK_PUSH, amount=amount, currency=currency, customer_phone=customer_phone, reference=reference)

    async def push_selcom_pesa(self, *, amount: Decimal, currency: str, customer_phone: str, reference: str) -> dict:
        return await self._push(_PATH_SELCOM_PESA_PUSH, amount=amount, currency=currency, customer_phone=customer_phone, reference=reference)

    async def create_dynamic_qr(self, *, amount: Decimal, currency: str, reference: str) -> dict:
        return await self._post(
            _PATH_DYNAMIC_QR,
            {"vendor": self._vendor_id, "order_id": reference, "amount": str(amount), "currency": currency},
        )

    async def get_order_status(self, *, provider_reference: str) -> dict:
        return await self._post(_PATH_ORDER_STATUS, {"vendor": self._vendor_id, "order_id": provider_reference})

    async def create_payout(
        self,
        *,
        amount: Decimal,
        currency: str,
        destination_identifier: str,
        reference: str,
        bank_name: str | None = None,
        network: str | None = None,
    ) -> dict:
        body = {
            "vendor": self._vendor_id,
            "order_id": reference,
            "amount": str(amount),
            "currency": currency,
            "destination": destination_identifier,
        }
        if bank_name:
            body["bank_name"] = bank_name
        if network:
            body["network"] = network
        return await self._post(_PATH_PAYOUT, body)


class LiveSelcomClient:
    """The PaymentProvider implementation used when SELCOM_MODE=live (see
    app/services/selcom/client.py::get_selcom_client()). Implements the
    exact same interface MockSelcomClient does (app/services/selcom/client.py's
    PaymentProvider Protocol) so nothing above this layer (routers,
    app/services/collections.py, app/services/disbursements.py) has to know
    or care which one is active.

    Despite the name, this class also handles disbursements/withdrawals
    (initiate_disbursement below) — it implements the *whole* PaymentProvider
    protocol, same as MockSelcomClient does. The withdrawal-specific payload
    construction and response parsing live in
    app/services/selcom/withdrawals.py; this class just delegates to it, the
    same way it delegates push/QR collection work to its own methods.
    """

    def __init__(self, *, client: SelcomHTTPClient):
        self._client = client

    async def initiate_collection(
        self,
        *,
        method: str,
        amount: Decimal,
        currency: str,
        customer_phone: str | None,
        reference: str,
    ) -> CollectionResult:
        if not customer_phone:
            raise ValueError(f"{method} requires a customer phone number")

        if method == "USSD_PUSH":
            response = await self._client.push_ussd(
                amount=amount, currency=currency, customer_phone=customer_phone, reference=reference
            )
        elif method == "STK_PUSH":
            response = await self._client.push_stk(
                amount=amount, currency=currency, customer_phone=customer_phone, reference=reference
            )
        elif method == "SELCOM_PESA_PUSH":
            response = await self._client.push_selcom_pesa(
                amount=amount, currency=currency, customer_phone=customer_phone, reference=reference
            )
        else:
            raise ValueError(f"Unsupported collection method for Selcom: {method}")

        return CollectionResult(
            provider=_CLIENT_NAME,
            provider_reference=extract_provider_reference(response) or reference,
            # A push always acks as processing — real resolution comes from
            # check_collection_status (below) or the /v1/webhooks/selcom
            # callback, never synchronously from the push call itself.
            status="processing",
        )

    async def check_collection_status(self, *, provider_reference: str) -> CollectionResult:
        response = await self._client.get_order_status(provider_reference=provider_reference)
        status = extract_status(response)
        failure_reason = None
        if status == "failed":
            failure_reason = str(
                response.get("message") or response.get("reason") or "Selcom reported this collection failed"
            )
        return CollectionResult(
            provider=_CLIENT_NAME, provider_reference=provider_reference, status=status, failure_reason=failure_reason
        )

    async def generate_dynamic_qr(self, *, amount: Decimal, currency: str, reference: str) -> DynamicQrResult:
        response = await self._client.create_dynamic_qr(amount=amount, currency=currency, reference=reference)
        data = response.get("data") if isinstance(response.get("data"), dict) else {}
        qr_payload = str(response.get("qrcode") or response.get("qr_payload") or data.get("qrcode") or "")
        expires_in_seconds = int(response.get("expiry") or response.get("expires_in") or 300)

        return DynamicQrResult(
            provider=_CLIENT_NAME,
            provider_reference=extract_provider_reference(response) or reference,
            qr_payload=qr_payload,
            qr_expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds),
        )

    async def initiate_disbursement(
        self,
        *,
        method: str,
        amount: Decimal,
        currency: str,
        destination_identifier: str,
        reference: str,
        bank_name: str | None = None,
        network: str | None = None,
    ) -> DisbursementResult:
        """Delegates to app/services/selcom/withdrawals.py — see that
        module for the method-aware payload construction. `bank_name`/
        `network` are optional because the PaymentProvider protocol's
        initiate_disbursement signature (client.py) doesn't carry them; only
        app/services/disbursements.py's Selcom-aware caller passes them."""
        return await initiate_withdrawal(
            self._client,
            method=method,
            amount=amount,
            currency=currency,
            destination_identifier=destination_identifier,
            bank_name=bank_name,
            network=network,
            reference=reference,
        )
