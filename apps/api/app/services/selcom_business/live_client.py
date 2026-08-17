"""The real Selcom Business Disbursement API client — constructed for both
SELCOM_BUSINESS_MODE="sandbox" and "live" (same code, different base_url/
credentials; see client.py::get_selcom_business_client()). Never
constructed for "mock".

**Unverified against a real sandbox round-trip** — the request shape
(headers, RSA-SHA256 signing string, endpoint paths, field names) comes
from developer.selcom.business's own landing page (fetched directly for
this integration), which is a real, current, documented spec — a
meaningfully stronger starting point than app/services/selcom/live_client.py's
"no documentation was available" placeholder. But the *response* body
shape wasn't shown there (see parsing.py's own caveat), and nothing here
has been exercised against Selcom's actual sandbox. Verify with a real
sandbox transaction before ever setting SELCOM_BUSINESS_MODE=live.

Never logs the request body, the private key, the API key, or a raw
recipient account — only path/status/latency, same convention as
app/services/selcom/live_client.py's SelcomHTTPClient._post().
"""

import logging
import time
import uuid

import httpx

from app.core.errors import SelcomAPIError
from app.services.selcom_business.parsing import parse_transaction_result
from app.services.selcom_business.schemas import SelcomBusinessResult
from app.services.selcom_business.signing import sign_request

logger = logging.getLogger("infinity.selcom_business")

_PATH_BALANCE = "/balance"
_PATH_ACCOUNT_LOOKUP = "/account/lookup"
_PATH_TRANSACTION_PROCESS = "/transaction/process"
_PATH_TRANSACTION_QUERY = "/transaction/query"


def generate_trans_id() -> str:
    return f"INF-{uuid.uuid4().hex[:16].upper()}"


class SelcomBusinessClient:
    def __init__(self, *, base_url: str, api_key: str, private_key_base64: str, timeout_seconds: int = 30):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._private_key_base64 = private_key_base64
        self._timeout_seconds = timeout_seconds

    def _build_url(self, path: str) -> str:
        # Selcom's own sandbox base ("https://sandbox.selcom.business") has
        # no /v1 prefix; the production base
        # ("https://api.selcom.business/v1") already includes it — normalize
        # here so swapping SELCOM_BUSINESS_MODE never silently 404s.
        base = self._base_url
        if base.endswith("/v1"):
            return f"{base}{path}"
        return f"{base}/v1{path}"

    async def _signed_request(self, method: str, path: str, fields: dict[str, str]) -> dict:
        timestamp, digest, signed_fields = sign_request(fields, private_key_base64=self._private_key_base64)
        headers = {
            "api-key": self._api_key,
            "timestamp": timestamp,
            "digest": digest,
            "signed-fields": signed_fields,
            "content-type": "application/json",
            "accept": "application/json",
        }
        url = self._build_url(path)

        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as http:
                if method == "GET":
                    response = await http.get(url, params=fields, headers=headers)
                else:
                    response = await http.post(url, json=fields, headers=headers)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPError) as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            logger.warning(
                "selcom_business_request_failed path=%s latency_ms=%d error=%s",
                path, latency_ms, type(exc).__name__,
            )
            raise SelcomAPIError(f"Could not reach Selcom Business API ({type(exc).__name__})") from exc

        latency_ms = int((time.monotonic() - started) * 1000)
        logger.info(
            "selcom_business_request path=%s status=%d latency_ms=%d", path, response.status_code, latency_ms
        )

        if response.status_code >= 400:
            raise SelcomAPIError(
                f"Selcom Business API returned HTTP {response.status_code} for {path}",
                provider_status_code=response.status_code,
            )

        try:
            return response.json()
        except ValueError as exc:
            raise SelcomAPIError(f"Selcom Business API returned a non-JSON response for {path}") from exc

    async def account_lookup(
        self, *, recipient_fi_code: str, recipient_account: str, trans_id: str, amount: str | None = None
    ) -> dict:
        fields = {"bank": recipient_fi_code, "account": recipient_account, "transId": trans_id}
        if amount is not None:
            fields["amount"] = amount
        return await self._signed_request("GET", _PATH_ACCOUNT_LOOKUP, fields)

    async def process_transaction(
        self,
        *,
        trans_id: str,
        recipient_fi_code: str,
        recipient_account: str,
        recipient_name: str,
        amount: str,
        purpose: str,
        remarks: str | None = None,
    ) -> SelcomBusinessResult:
        fields = {
            "transId": trans_id,
            "recipientFiCode": recipient_fi_code,
            "recipientAccount": recipient_account,
            "recipientName": recipient_name,
            "amount": amount,
            "purpose": purpose,
        }
        if remarks:
            fields["remarks"] = remarks
        response = await self._signed_request("POST", _PATH_TRANSACTION_PROCESS, fields)
        return parse_transaction_result(response, trans_id=trans_id)

    async def query_transaction(self, *, trans_id: str) -> SelcomBusinessResult:
        response = await self._signed_request("GET", _PATH_TRANSACTION_QUERY, {"transId": trans_id})
        return parse_transaction_result(response, trans_id=trans_id)

    async def balance(self, *, account_number: str) -> dict:
        return await self._signed_request("POST", _PATH_BALANCE, {"account_number": account_number})
