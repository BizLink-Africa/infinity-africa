"""app/services/selcom_business/ — mode branching (get_selcom_business_client),
RSA-SHA256 signing shape, URL normalization, and the mock client's basic
behavior. This is a distinct product/client from app/services/selcom/ (see
tests/test_selcom_signature.py / test_selcom_live_client.py for the
checkout/collections side, untouched by this work).
"""

import base64

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import get_settings
from app.services.selcom_business.client import get_selcom_business_client
from app.services.selcom_business.live_client import SelcomBusinessClient
from app.services.selcom_business.mock_client import MockSelcomBusinessClient
from app.services.selcom_business.signing import sign_request


def _generate_test_private_key_base64() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return base64.b64encode(pem).decode("ascii")


@pytest.fixture(autouse=True)
def _clear_caches():
    get_settings.cache_clear()
    get_selcom_business_client.cache_clear()
    yield
    get_settings.cache_clear()
    get_selcom_business_client.cache_clear()


# --- mode branching ------------------------------------------------------------


def test_mock_mode_never_constructs_the_real_client(monkeypatch):
    monkeypatch.setenv("SELCOM_BUSINESS_MODE", "mock")
    get_settings.cache_clear()

    provider = get_selcom_business_client()

    assert isinstance(provider, MockSelcomBusinessClient)
    assert not isinstance(provider, SelcomBusinessClient)


def test_sandbox_mode_never_constructs_the_mock_client(monkeypatch):
    monkeypatch.setenv("SELCOM_BUSINESS_MODE", "sandbox")
    get_settings.cache_clear()

    provider = get_selcom_business_client()

    assert isinstance(provider, SelcomBusinessClient)
    assert not isinstance(provider, MockSelcomBusinessClient)


def test_live_mode_never_constructs_the_mock_client(monkeypatch):
    monkeypatch.setenv("SELCOM_BUSINESS_MODE", "live")
    get_settings.cache_clear()

    provider = get_selcom_business_client()

    assert isinstance(provider, SelcomBusinessClient)
    assert not isinstance(provider, MockSelcomBusinessClient)


def test_sandbox_and_live_point_at_different_base_urls(monkeypatch):
    monkeypatch.setenv("SELCOM_BUSINESS_MODE", "sandbox")
    get_settings.cache_clear()
    sandbox_client = get_selcom_business_client()
    assert sandbox_client._base_url == "https://sandbox.selcom.business"

    get_selcom_business_client.cache_clear()
    monkeypatch.setenv("SELCOM_BUSINESS_MODE", "live")
    get_settings.cache_clear()
    live_client = get_selcom_business_client()
    assert live_client._base_url == "https://api.selcom.business/v1"


# --- URL normalization (sandbox base has no /v1, production base already does) ---


def test_build_url_adds_v1_prefix_for_sandbox_style_base():
    client = SelcomBusinessClient(
        base_url="https://sandbox.selcom.business", api_key="k", private_key_base64="", timeout_seconds=30
    )
    assert client._build_url("/transaction/process") == "https://sandbox.selcom.business/v1/transaction/process"


def test_build_url_does_not_double_up_v1_for_production_style_base():
    client = SelcomBusinessClient(
        base_url="https://api.selcom.business/v1", api_key="k", private_key_base64="", timeout_seconds=30
    )
    assert client._build_url("/transaction/process") == "https://api.selcom.business/v1/transaction/process"


# --- RSA-SHA256 signing ---------------------------------------------------------


def test_sign_request_produces_documented_header_shape():
    private_key_base64 = _generate_test_private_key_base64()
    fields = {"transId": "INF-1", "recipientFiCode": "MPESA", "recipientAccount": "255747730270", "amount": "1000"}

    timestamp, digest, signed_fields = sign_request(fields, private_key_base64=private_key_base64)

    assert timestamp.endswith("Z")
    assert signed_fields == "transId,recipientFiCode,recipientAccount,amount"
    # digest is base64 of an RSA-2048 SHA256 signature -> 256 bytes -> 344 base64 chars (with padding)
    assert len(base64.b64decode(digest)) == 256


def test_sign_request_is_deterministic_for_a_fixed_timestamp():
    private_key_base64 = _generate_test_private_key_base64()
    fields = {"transId": "INF-1", "amount": "1000"}

    _, digest_a, _ = sign_request(fields, private_key_base64=private_key_base64, timestamp="2026-05-27T06:01:03.273Z")
    _, digest_b, _ = sign_request(fields, private_key_base64=private_key_base64, timestamp="2026-05-27T06:01:03.273Z")

    assert digest_a == digest_b


def test_sign_request_changes_digest_when_fields_change():
    private_key_base64 = _generate_test_private_key_base64()
    ts = "2026-05-27T06:01:03.273Z"

    _, digest_a, _ = sign_request({"amount": "1000"}, private_key_base64=private_key_base64, timestamp=ts)
    _, digest_b, _ = sign_request({"amount": "2000"}, private_key_base64=private_key_base64, timestamp=ts)

    assert digest_a != digest_b


# --- mock client -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_mock_process_transaction_always_succeeds_at_zero_failure_rate():
    provider = MockSelcomBusinessClient(failure_rate=0.0, latency_seconds=0)

    result = await provider.process_transaction(
        trans_id="INF-1",
        recipient_fi_code="MPESA",
        recipient_account="255747730270",
        recipient_name="Jane Doe",
        amount="1000",
        purpose="withdrawal",
    )

    assert result.status == "successful"
    assert result.transaction_id == "INF-1"


@pytest.mark.asyncio
async def test_mock_process_transaction_always_fails_at_full_failure_rate():
    provider = MockSelcomBusinessClient(failure_rate=1.0, latency_seconds=0)

    result = await provider.process_transaction(
        trans_id="INF-2",
        recipient_fi_code="CRDB",
        recipient_account="0151234567890",
        recipient_name="Jane Doe",
        amount="1000",
        purpose="withdrawal",
    )

    assert result.status == "failed"
    assert result.failure_reason is not None


@pytest.mark.asyncio
async def test_mock_query_transaction_resolves_successfully():
    provider = MockSelcomBusinessClient(failure_rate=0.0, latency_seconds=0)

    result = await provider.query_transaction(trans_id="INF-3")

    assert result.status == "successful"
    assert result.transaction_id == "INF-3"
