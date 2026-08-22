"""app/services/selcom_checkout/{client,parsing}.py —
GET /v1/checkout/order-status?order_id={order_id}. Signed-Fields is just
`order_id` per the reconciliation task brief. Field-name confidence
level: see parsing.py's module docstring (recovered from the task brief,
not yet independently re-verified against a live call the way
create-order-minimal was).
"""

import json
from typing import ClassVar

import pytest

import app.services.selcom_checkout.client as selcom_checkout_client_module
from app.services.selcom_checkout.client import SelcomCheckoutHTTPClient
from app.services.selcom_checkout.parsing import parse_order_status_response
from app.services.selcom_checkout.schemas import SelcomCheckoutCredentials

REAL_STYLE_COMPLETED_RESPONSE = {
    "reference": "S20690471578",
    "resultcode": "000",
    "result": "SUCCESS",
    "message": "Order status retrieved",
    "data": [
        {
            "order_id": "ORD-20260823-ABCD1234",
            "creation_date": "2026-08-23 10:00:00",
            "amount": "1000.00",
            "payment_status": "COMPLETED",
            "transid": "TXN-20260823-EFGH5678",
            "channel": "TIGOPESA",
            "reference": "S20690471578",
            "phone": "255747730270",
        }
    ],
}

REAL_STYLE_PENDING_RESPONSE = {
    "reference": "S20690471579",
    "resultcode": "000",
    "result": "SUCCESS",
    "message": "Order status retrieved",
    "data": [
        {
            "order_id": "ORD-20260823-ABCD1234",
            "creation_date": "2026-08-23 10:00:00",
            "amount": "1000.00",
            "payment_status": "PENDING",
            "transid": "TXN-20260823-EFGH5678",
            "channel": "TIGOPESA",
        }
    ],
}


# --- parsing ---------------------------------------------------------------------


def test_completed_order_status_parses_every_documented_field():
    result = parse_order_status_response(REAL_STYLE_COMPLETED_RESPONSE)

    assert result.reference == "S20690471578"
    assert result.resultcode == "000"
    assert result.result == "SUCCESS"
    assert result.order_id == "ORD-20260823-ABCD1234"
    assert result.creation_date == "2026-08-23 10:00:00"
    assert result.amount == "1000.00"
    assert result.payment_status == "COMPLETED"
    assert result.transid == "TXN-20260823-EFGH5678"
    assert result.channel == "TIGOPESA"
    assert result.phone == "255747730270"
    assert result.raw_response == REAL_STYLE_COMPLETED_RESPONSE


def test_per_order_reference_preferred_over_top_level_when_both_present():
    response = {**REAL_STYLE_COMPLETED_RESPONSE}
    response["data"] = [{**response["data"][0], "reference": "PER-ORDER-REF"}]
    result = parse_order_status_response(response)
    assert result.reference == "PER-ORDER-REF"


def test_falls_back_to_top_level_reference_when_data_lacks_one():
    response = {**REAL_STYLE_PENDING_RESPONSE}  # data has no "reference" key
    result = parse_order_status_response(response)
    assert result.reference == "S20690471579"


def test_phone_falls_back_to_msisdn_field_name():
    response = {**REAL_STYLE_COMPLETED_RESPONSE}
    data = dict(response["data"][0])
    del data["phone"]
    data["msisdn"] = "255747730270"
    response = {**response, "data": [data]}
    result = parse_order_status_response(response)
    assert result.phone == "255747730270"


def test_missing_data_does_not_crash():
    result = parse_order_status_response({"reference": "REF-1", "resultcode": "000", "result": "SUCCESS"})
    assert result.order_id is None
    assert result.payment_status is None


# --- client: signing ---------------------------------------------------------------


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

    async def request(self, method, url, *, params=None, json=None, headers=None):
        _FakeAsyncClient.calls.append({"method": method, "url": url, "params": params, "json": json, "headers": headers})
        return _FakeAsyncClient._next_response


@pytest.fixture(autouse=True)
def _patch_httpx(monkeypatch):
    monkeypatch.setattr(selcom_checkout_client_module.httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient._next_response = _FakeResponse(200, REAL_STYLE_COMPLETED_RESPONSE)
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
async def test_get_order_status_is_a_get_request_signed_with_order_id_only():
    result = await _client().get_order_status(order_id="ORD-20260823-ABCD1234")

    assert result.payment_status == "COMPLETED"

    call = _FakeAsyncClient.calls[0]
    assert call["method"] == "GET"
    assert call["url"] == "https://checkout.example.selcommobile.com/v1/checkout/order-status"
    assert call["params"] == {"order_id": "ORD-20260823-ABCD1234"}
    assert call["json"] is None
    assert call["headers"]["Signed-Fields"] == "order_id"


@pytest.mark.asyncio
async def test_get_order_status_never_sends_api_secret():
    await _client().get_order_status(order_id="ORD-1")

    call = _FakeAsyncClient.calls[0]
    assert "test-secret" not in json.dumps(call["headers"])
