"""Simulates Selcom's checkout/collections API — the default client
(SELCOM_MODE=mock) for local development and for production until Selcom
whitelists this backend's Railway static outbound IP (see
docs/selcom-live-go-live.md). It takes the same inputs live_client.py's
LiveSelcomClient would, waits a plausible amount of time, and returns a
plausible outcome — including simulated failures, so error-path code isn't
developed against an implementation that always succeeds.

Collections model the realistic two-step shape of a push/QR payment: the
initiate/generate calls ack fast with "processing" (a real push API
responds near-instantly — it's the customer's approval that takes time);
check_collection_status simulates that approval delay and applies the
failure rate.

Withdrawals/disbursements are a different Selcom product (the Business
Disbursement API) with their own mock client — see
app/services/selcom_business/mock_client.py.
"""

import asyncio
import random
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.services.selcom.schemas import (
    CollectionResult,
    DynamicQrResult,
)

_CLIENT_NAME = "mock_selcom"

# Real push-payment APIs ack the request itself almost immediately — the
# initiate_collection()/generate_dynamic_qr() latency below is capped to
# this regardless of the configured mock latency, which models the much
# longer customer-approval wait simulated in check_collection_status.
_ACK_LATENCY_SECONDS = 0.2


class MockSelcomClient:
    def __init__(
        self,
        *,
        failure_rate: float = 0.1,
        latency_seconds: float = 0.3,
        qr_expiry_seconds: int = 300,
    ):
        self.failure_rate = failure_rate
        self.latency_seconds = latency_seconds
        self.qr_expiry_seconds = qr_expiry_seconds

    async def initiate_collection(
        self,
        *,
        method: str,
        amount: Decimal,
        currency: str,
        customer_phone: str | None,
        reference: str,
    ) -> CollectionResult:
        await asyncio.sleep(min(self.latency_seconds, _ACK_LATENCY_SECONDS))
        return CollectionResult(
            provider=_CLIENT_NAME,
            provider_reference=_generate_provider_reference(),
            status="processing",
        )

    async def check_collection_status(self, *, provider_reference: str) -> CollectionResult:
        await asyncio.sleep(self.latency_seconds)

        if random.random() < self.failure_rate:
            return CollectionResult(
                provider=_CLIENT_NAME,
                provider_reference=provider_reference,
                status="failed",
                failure_reason=random.choice(
                    ["Insufficient balance", "Customer cancelled the push", "Network timeout"]
                ),
            )

        return CollectionResult(provider=_CLIENT_NAME, provider_reference=provider_reference, status="successful")

    async def generate_dynamic_qr(
        self,
        *,
        amount: Decimal,
        currency: str,
        reference: str,
    ) -> DynamicQrResult:
        await asyncio.sleep(min(self.latency_seconds, _ACK_LATENCY_SECONDS))
        provider_reference = _generate_provider_reference()
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.qr_expiry_seconds)

        # A real Selcom QR payload has its own defined encoding; this is
        # just a plausible stand-in carrying enough to be visibly a mock.
        qr_payload = (
            f"selcompay://qr?ref={provider_reference}&amount={amount}"
            f"&currency={currency}&merchant_ref={reference}"
        )

        return DynamicQrResult(
            provider=_CLIENT_NAME,
            provider_reference=provider_reference,
            qr_payload=qr_payload,
            qr_expires_at=expires_at,
        )


def _generate_provider_reference() -> str:
    return f"MOCK-SELCOM-{uuid.uuid4().hex[:12].upper()}"
