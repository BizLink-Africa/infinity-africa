"""The Selcom Business Disbursement API adapter interface, and the one
place mock vs. sandbox vs. live is decided — mirrors
app/services/selcom/client.py's role for the (unrelated, differently-signed)
checkout/collections API.

SELCOM_BUSINESS_MODE controls which client get_selcom_business_client()
returns:
  - "mock"    -> MockSelcomBusinessClient. Local development only. Never
                 reachable when mode is "sandbox" or "live" — there is no
                 code path that falls back to the mock client from either.
  - "sandbox" -> SelcomBusinessClient pointed at
                 SELCOM_BUSINESS_SANDBOX_BASE_URL. Real HTTP calls to
                 Selcom's sandbox environment.
  - "live"    -> SelcomBusinessClient pointed at
                 SELCOM_BUSINESS_PRODUCTION_BASE_URL. Real HTTP calls to
                 Selcom's production environment — only use once a real
                 sandbox round-trip has verified the request/response shapes
                 in app/services/selcom_business/signing.py and parsing.py.

Only app/services/disbursements.py's Super-Admin-approval path ever calls
this — never the merchant submission path (see execute_disbursement, which
never imports this module at all).
"""

from functools import lru_cache
from typing import Protocol

from app.config import get_settings
from app.services.selcom_business.schemas import SelcomBusinessResult


class SelcomBusinessProvider(Protocol):
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
    ) -> SelcomBusinessResult: ...

    async def query_transaction(self, *, trans_id: str) -> SelcomBusinessResult: ...


@lru_cache
def get_selcom_business_client() -> SelcomBusinessProvider:
    """Cached like get_selcom_client() — constructing either client is
    cheap and stateless; tests that flip SELCOM_BUSINESS_MODE between cases
    must call get_selcom_business_client.cache_clear()."""
    settings = get_settings()

    if settings.selcom_business_mode == "mock":
        from app.services.selcom_business.mock_client import MockSelcomBusinessClient

        return MockSelcomBusinessClient(
            failure_rate=settings.mock_provider_failure_rate,
            latency_seconds=settings.mock_provider_latency_seconds,
        )

    from app.services.selcom_business.live_client import SelcomBusinessClient

    base_url = (
        settings.selcom_business_production_base_url
        if settings.selcom_business_mode == "live"
        else settings.selcom_business_sandbox_base_url
    )
    return SelcomBusinessClient(
        base_url=base_url,
        api_key=settings.selcom_business_api_key,
        private_key_base64=settings.selcom_business_private_key_base64,
        timeout_seconds=settings.selcom_business_timeout_seconds,
    )


__all__ = ["SelcomBusinessProvider", "SelcomBusinessResult", "get_selcom_business_client"]
