"""Unit tests for app/services/selcom/live_client.py's HTTP/error-handling
shell — no real network call is made; httpx.AsyncClient is replaced with a
fake that hands back a scripted response (or raises), so these exercise the
retry/error-mapping logic in SelcomHTTPClient._post() in isolation from
whatever Selcom's real API actually returns (see the module's docstring
caveat)."""

from decimal import Decimal

import httpx
import pytest

from app.core.errors import SelcomAPIError
from app.services.selcom import live_client as selcom_live_client_module
from app.services.selcom.live_client import SelcomHTTPClient


class _FakeResponse:
    def __init__(self, status_code: int, json_body: dict | None = None, raise_on_json: bool = False):
        self.status_code = status_code
        self._json_body = json_body
        self._raise_on_json = raise_on_json

    def json(self):
        if self._raise_on_json:
            raise ValueError("not json")
        return self._json_body


class _FakeAsyncClient:
    """Stands in for httpx.AsyncClient — SelcomHTTPClient constructs a
    fresh one per call, so this fakes exactly that one entry point
    (`.post`)."""

    _next_response: _FakeResponse | Exception | None = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, *, content, headers):
        if isinstance(_FakeAsyncClient._next_response, Exception):
            raise _FakeAsyncClient._next_response
        return _FakeAsyncClient._next_response


@pytest.fixture(autouse=True)
def _patch_httpx(monkeypatch):
    monkeypatch.setattr(selcom_live_client_module.httpx, "AsyncClient", _FakeAsyncClient)
    monkeypatch.setattr(selcom_live_client_module, "_MAX_CONNECT_RETRIES", 0)
    yield
    _FakeAsyncClient._next_response = None


def _client() -> SelcomHTTPClient:
    return SelcomHTTPClient(base_url="https://selcom.example", api_key="key", api_secret="secret", vendor_id="VENDOR-1")


@pytest.mark.asyncio
async def test_push_ussd_returns_parsed_json_on_success():
    _FakeAsyncClient._next_response = _FakeResponse(200, {"result": "success", "reference": "SEL-1"})

    result = await _client().push_ussd(
        amount=Decimal(1000), currency="TZS", customer_phone="+255700000000", reference="COL-1"
    )

    assert result == {"result": "success", "reference": "SEL-1"}


@pytest.mark.asyncio
async def test_non_2xx_response_raises_selcom_api_error():
    _FakeAsyncClient._next_response = _FakeResponse(500, {"error": "boom"})

    with pytest.raises(SelcomAPIError):
        await _client().push_stk(
            amount=Decimal(1000), currency="TZS", customer_phone="+255700000000", reference="COL-1"
        )


@pytest.mark.asyncio
async def test_non_json_response_raises_selcom_api_error():
    _FakeAsyncClient._next_response = _FakeResponse(200, raise_on_json=True)

    with pytest.raises(SelcomAPIError):
        await _client().create_dynamic_qr(amount=Decimal(1000), currency="TZS", reference="COL-1")


@pytest.mark.asyncio
async def test_connection_error_raises_selcom_api_error_not_the_raw_exception():
    _FakeAsyncClient._next_response = httpx.ConnectError("connection refused")

    with pytest.raises(SelcomAPIError):
        await _client().get_order_status(provider_reference="SEL-1")
