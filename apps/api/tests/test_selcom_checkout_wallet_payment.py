"""app/services/selcom_checkout/{parsing,client}.py — wallet-payment
(POST /v1/checkout/wallet-payment) response parsing and request
construction, against the sample response given in the task brief:

    {"reference": "0289999288", "resultcode": "111", "result": "PENDING",
     "message": "Request in progress. You will receive a callback shortly.",
     "data": []}

PENDING/111 is the *normal* outcome for this endpoint — Selcom resolves
the actual push result asynchronously. See WalletPaymentResult's
docstring for why status mapping never collapses this into success or
failure.
"""

import json
from typing import ClassVar

import pytest

import app.services.selcom_checkout.client as selcom_checkout_client_module
from app.services.selcom_checkout.client import SelcomCheckoutHTTPClient
from app.services.selcom_checkout.parsing import parse_wallet_payment_response
from app.services.selcom_checkout.schemas import SelcomCheckoutCredentials

REAL_PENDING_RESPONSE = {
    "reference": "0289999288",
    "resultcode": "111",
    "result": "PENDING",
    "message": "Request in progress. You will receive a callback shortly.",
    "data": [],
}


# --- parsing: status mapping --------------------------------------------------------


def test_pending_111_maps_to_processing_not_failure():
    result = parse_wallet_payment_response(REAL_PENDING_RESPONSE)

    assert result.status == "processing"
    assert result.resultcode == "111"
    assert result.result == "PENDING"
    assert result.reference == "0289999288"
    assert result.message == "Request in progress. You will receive a callback shortly."
    assert result.raw_response == REAL_PENDING_RESPONSE


def test_resultcode_927_also_maps_to_processing():
    response = {**REAL_PENDING_RESPONSE, "resultcode": "927", "result": "INPROGRESS"}
    result = parse_wallet_payment_response(response)
    assert result.status == "processing"


def test_resultcode_000_maps_to_successful():
    response = {"reference": "REF-1", "resultcode": "000", "result": "SUCCESS", "message": "OK", "data": []}
    result = parse_wallet_payment_response(response)
    assert result.status == "successful"


def test_result_success_without_matching_resultcode_still_maps_to_successful():
    response = {"reference": "REF-1", "resultcode": "200", "result": "SUCCESS", "message": "OK", "data": []}
    result = parse_wallet_payment_response(response)
    assert result.status == "successful"


def test_resultcode_999_maps_to_ambiguous():
    response = {"reference": "REF-1", "resultcode": "999", "result": "UNKNOWN", "message": "?", "data": []}
    result = parse_wallet_payment_response(response)
    assert result.status == "ambiguous"


def test_unrecognized_resultcode_maps_to_failed():
    response = {"reference": "REF-1", "resultcode": "651", "result": "FAIL", "message": "Invalid", "data": []}
    result = parse_wallet_payment_response(response)
    assert result.status == "failed"


def test_missing_fields_do_not_crash():
    result = parse_wallet_payment_response({})
    assert result.status == "failed"
    assert result.reference == ""
    assert result.resultcode == ""


# --- client: request construction ---------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code: int, json_body: dict):
        self.status_code = status_code
        self.content = json.dumps(json_body).encode("utf-8")


class _FakeAsyncClient:
    _next_response: _FakeResponse | None = None
    calls: ClassVar[list[dict]] = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def request(self, method, url, *, json, headers):
        _FakeAsyncClient.calls.append({"method": method, "url": url, "json": json, "headers": headers})
        return _FakeAsyncClient._next_response


@pytest.fixture(autouse=True)
def _patch_httpx(monkeypatch):
    monkeypatch.setattr(selcom_checkout_client_module.httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient._next_response = _FakeResponse(200, REAL_PENDING_RESPONSE)
    _FakeAsyncClient.calls = []
    yield
    _FakeAsyncClient._next_response = None
    _FakeAsyncClient.calls = []


def _client() -> SelcomCheckoutHTTPClient:
    credentials = SelcomCheckoutCredentials(
        base_url="https://checkout.example.selcommobile.com",
        api_key="test-key",
        api_secret="test-secret",
        digest_method="HS256",
        vendor="VENDORTEST",
        timeout_seconds=30,
    )
    return SelcomCheckoutHTTPClient(credentials=credentials)


@pytest.mark.asyncio
async def test_wallet_payment_signs_fields_in_the_documented_order():
    result = await _client().process_wallet_payment(transid="TXN-1", order_id="ORD-1", msisdn="255747730270")

    assert result.status == "processing"

    call = _FakeAsyncClient.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "https://checkout.example.selcommobile.com/v1/checkout/wallet-payment"
    assert list(call["json"].keys()) == ["transid", "order_id", "msisdn"]
    assert call["json"] == {"transid": "TXN-1", "order_id": "ORD-1", "msisdn": "255747730270"}
    assert call["headers"]["Signed-Fields"] == "transid,order_id,msisdn"


@pytest.mark.asyncio
async def test_wallet_payment_never_sends_api_secret():
    await _client().process_wallet_payment(transid="TXN-1", order_id="ORD-1", msisdn="255747730270")

    call = _FakeAsyncClient.calls[0]
    assert "test-secret" not in json.dumps(call["json"])
    assert "test-secret" not in json.dumps(call["headers"])


@pytest.mark.asyncio
async def test_wallet_payment_url_collapses_duplicated_v1_segment():
    credentials = SelcomCheckoutCredentials(
        base_url="https://apigw.selcommobile.com/v1", api_key="k", api_secret="s", vendor="V"
    )
    await SelcomCheckoutHTTPClient(credentials=credentials).process_wallet_payment(
        transid="TXN-1", order_id="ORD-1", msisdn="255747730270"
    )

    call = _FakeAsyncClient.calls[0]
    assert call["url"] == "https://apigw.selcommobile.com/v1/checkout/wallet-payment"
