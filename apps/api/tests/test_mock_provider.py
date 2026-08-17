from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.services.selcom.mock_client import MockSelcomClient


@pytest.mark.asyncio
async def test_initiate_collection_always_returns_processing():
    """A push ack is fast and always "processing" — the failure_rate only
    applies once check_collection_status simulates the customer's response."""
    provider = MockSelcomClient(failure_rate=1.0, latency_seconds=0)

    result = await provider.initiate_collection(
        method="STK_PUSH", amount=Decimal(1000), currency="TZS", customer_phone="+255700000000", reference="X"
    )

    assert result.status == "processing"
    assert result.provider_reference.startswith("MOCK-SELCOM-")
    assert result.failure_reason is None


@pytest.mark.asyncio
async def test_check_collection_status_succeeds_at_zero_failure_rate():
    provider = MockSelcomClient(failure_rate=0.0, latency_seconds=0)

    result = await provider.check_collection_status(provider_reference="MOCK-SELCOM-ABC123")

    assert result.status == "successful"
    assert result.provider_reference == "MOCK-SELCOM-ABC123"
    assert result.failure_reason is None


@pytest.mark.asyncio
async def test_check_collection_status_fails_at_full_failure_rate():
    provider = MockSelcomClient(failure_rate=1.0, latency_seconds=0)

    result = await provider.check_collection_status(provider_reference="MOCK-SELCOM-ABC123")

    assert result.status == "failed"
    assert result.failure_reason is not None


@pytest.mark.asyncio
async def test_provider_references_are_unique():
    provider = MockSelcomClient(failure_rate=0.0, latency_seconds=0)

    first = await provider.initiate_collection(
        method="STK_PUSH", amount=Decimal(1), currency="TZS", customer_phone=None, reference="A"
    )
    second = await provider.initiate_collection(
        method="STK_PUSH", amount=Decimal(1), currency="TZS", customer_phone=None, reference="B"
    )

    assert first.provider_reference != second.provider_reference


@pytest.mark.asyncio
async def test_generate_dynamic_qr_returns_payload_and_future_expiry():
    provider = MockSelcomClient(latency_seconds=0, qr_expiry_seconds=300)

    result = await provider.generate_dynamic_qr(amount=Decimal(2500), currency="TZS", reference="COL-1")

    assert result.provider_reference.startswith("MOCK-SELCOM-")
    assert "COL-1" in result.qr_payload
    assert "2500" in result.qr_payload
    assert result.qr_expires_at > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_generate_dynamic_qr_expiry_matches_configured_window():
    provider = MockSelcomClient(latency_seconds=0, qr_expiry_seconds=60)

    before = datetime.now(timezone.utc)
    result = await provider.generate_dynamic_qr(amount=Decimal(100), currency="TZS", reference="COL-2")

    delta = (result.qr_expires_at - before).total_seconds()
    assert 55 <= delta <= 65
