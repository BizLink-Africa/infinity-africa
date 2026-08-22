"""app/services/selcom_checkout/client.py — SelcomCheckoutHTTPClient's
generic signed-request plumbing and create_order_minimal()'s field
construction, against a fake httpx.AsyncClient (no real network call).
Response-shape assertions live in test_selcom_checkout_parsing.py;
signing-math assertions live in test_selcom_checkout_signing.py — this
file is about what actually gets sent on the wire.
"""

import json
from typing import ClassVar

import pytest

import app.services.selcom_checkout.client as selcom_checkout_client_module
from app.core.errors import SelcomAPIError
from app.services.selcom_checkout.client import SelcomCheckoutHTTPClient, _join_url
from app.services.selcom_checkout.errors import SelcomCheckoutMisconfiguredError
from app.services.selcom_checkout.schemas import SelcomCheckoutCredentials

REAL_SUCCESS_RESPONSE = {
    "reference": "0289999288",
    "resultcode": "000",
    "result": "SUCCESS",
    "message": "Payment notification logged",
    "data": [
        {
            "gateway_buyer_uuid": "12344321",
            "payment_token": "80008000",
            "qr": "QR",
            "payment_gateway_url": "aHR0cDpleGFtcGxlLmNvbS9wZy90MTIyMjI=",
        }
    ],
}


class _FakeResponse:
    def __init__(self, status_code: int, json_body: dict):
        self.status_code = status_code
        self.content = json.dumps(json_body).encode("utf-8")


class _FakeAsyncClient:
    """Stands in for httpx.AsyncClient — mirrors
    test_selcom_business_client.py's identical fake for the (unrelated)
    Business Disbursement client. Captures every call so tests can
    inspect exactly what was sent."""

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
    _FakeAsyncClient._next_response = _FakeResponse(200, REAL_SUCCESS_RESPONSE)
    _FakeAsyncClient.calls = []
    yield
    _FakeAsyncClient._next_response = None
    _FakeAsyncClient.calls = []


def _client(**overrides) -> SelcomCheckoutHTTPClient:
    credentials = SelcomCheckoutCredentials(
        base_url="https://checkout.example.selcommobile.com",
        api_key="test-key",
        api_secret="test-secret",
        digest_method="HS256",
        vendor="VENDORTEST",
        timeout_seconds=30,
        **overrides,
    )
    return SelcomCheckoutHTTPClient(credentials=credentials)


# --- URL joining ------------------------------------------------------------------
#
# Confirmed against real production Selcom infrastructure (2026-08-22):
# SELCOM_CHECKOUT_BASE_URL is "https://apigw.selcommobile.com/v1", and
# every path constant here already starts with "/v1/..." — naive
# concatenation produced ".../v1/v1/checkout/create-order-minimal" and a
# real HTTP 404 from Selcom before this was fixed.


def test_join_url_collapses_duplicated_v1_segment():
    url = _join_url("https://apigw.selcommobile.com/v1", "/v1/checkout/create-order-minimal")
    assert url == "https://apigw.selcommobile.com/v1/checkout/create-order-minimal"


def test_join_url_collapses_duplicated_v1_segment_with_trailing_slash_on_base():
    url = _join_url("https://apigw.selcommobile.com/v1/", "/v1/checkout/create-order-minimal")
    assert url == "https://apigw.selcommobile.com/v1/checkout/create-order-minimal"


def test_join_url_is_a_no_op_when_base_has_no_version_segment():
    url = _join_url("https://apigw.selcommobile.com", "/v1/checkout/create-order-minimal")
    assert url == "https://apigw.selcommobile.com/v1/checkout/create-order-minimal"


# --- construction guards -------------------------------------------------------------


def test_missing_base_url_raises_misconfigured():
    credentials = SelcomCheckoutCredentials(base_url="", api_key="k")
    with pytest.raises(SelcomCheckoutMisconfiguredError):
        SelcomCheckoutHTTPClient(credentials=credentials)


def test_missing_api_key_raises_misconfigured():
    credentials = SelcomCheckoutCredentials(base_url="https://x.example.com", api_key="")
    with pytest.raises(SelcomCheckoutMisconfiguredError):
        SelcomCheckoutHTTPClient(credentials=credentials)


# --- create_order_minimal() field construction ----------------------------------------


@pytest.mark.asyncio
async def test_create_order_minimal_sends_documented_fields_in_order():
    result = await _client().create_order_minimal(
        order_id="ORD-1",
        buyer_email="john@example.com",
        buyer_name="John Joh",
        buyer_phone="255682000000",
        amount="8000",
        no_of_items=1,
        timestamp="2026-08-22T12:00:00.000Z",
    )

    assert result.reference == "0289999288"
    assert result.is_success is True

    call = _FakeAsyncClient.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "https://checkout.example.selcommobile.com/v1/checkout/create-order-minimal"
    assert list(call["json"].keys()) == [
        "vendor",
        "order_id",
        "buyer_email",
        "buyer_name",
        "buyer_phone",
        "amount",
        "currency",
        "no_of_items",
    ]
    assert call["headers"]["Signed-Fields"] == "vendor,order_id,buyer_email,buyer_name,buyer_phone,amount,currency,no_of_items"
    assert call["headers"]["Timestamp"] == "2026-08-22T12:00:00.000Z"
    assert call["headers"]["Vendor"] == "VENDORTEST"


@pytest.mark.asyncio
async def test_create_order_minimal_omits_optional_fields_when_absent():
    await _client().create_order_minimal(
        order_id="ORD-1",
        buyer_email="john@example.com",
        buyer_name="John Joh",
        buyer_phone="255682000000",
        amount="8000",
        no_of_items=1,
    )

    call = _FakeAsyncClient.calls[0]
    assert "redirect_url" not in call["json"]
    assert "cancel_url" not in call["json"]
    assert "webhook" not in call["json"]
    assert "buyer_remarks" not in call["json"]
    assert "merchant_remarks" not in call["json"]
    assert "redirect_url" not in call["headers"]["Signed-Fields"]


@pytest.mark.asyncio
async def test_create_order_minimal_includes_optional_fields_when_present_in_order():
    await _client().create_order_minimal(
        order_id="ORD-1",
        buyer_email="john@example.com",
        buyer_name="John Joh",
        buyer_phone="255682000000",
        amount="8000",
        no_of_items=1,
        redirect_url="https://example.com/redirect",
        cancel_url="https://example.com/cancel",
        webhook="https://example.com/webhook",
        buyer_remarks="None",
        merchant_remarks="None",
    )

    call = _FakeAsyncClient.calls[0]
    assert list(call["json"].keys()) == [
        "vendor",
        "order_id",
        "buyer_email",
        "buyer_name",
        "buyer_phone",
        "amount",
        "currency",
        "redirect_url",
        "cancel_url",
        "webhook",
        "buyer_remarks",
        "merchant_remarks",
        "no_of_items",
    ]


@pytest.mark.asyncio
async def test_signed_fields_matches_the_full_documented_default_order_exactly():
    """The exact string given in the task brief, byte for byte, when
    every optional field up to no_of_items is present."""
    await _client().create_order_minimal(
        order_id="ORD-1",
        buyer_email="john@example.com",
        buyer_name="John Joh",
        buyer_phone="255682000000",
        amount="8000",
        no_of_items=1,
        redirect_url="https://example.com/redirect",
        cancel_url="https://example.com/cancel",
        webhook="https://example.com/webhook",
        buyer_remarks="None",
        merchant_remarks="None",
    )

    call = _FakeAsyncClient.calls[0]
    assert call["headers"]["Signed-Fields"] == (
        "vendor,order_id,buyer_email,buyer_name,buyer_phone,amount,currency,"
        "redirect_url,cancel_url,webhook,buyer_remarks,merchant_remarks,no_of_items"
    )


@pytest.mark.asyncio
async def test_signed_fields_matches_the_documented_omitted_optional_example_exactly():
    """The exact string given in the task brief, byte for byte, when
    redirect_url/cancel_url/webhook are absent."""
    await _client().create_order_minimal(
        order_id="ORD-1",
        buyer_email="john@example.com",
        buyer_name="John Joh",
        buyer_phone="255682000000",
        amount="8000",
        no_of_items=1,
        buyer_remarks="None",
        merchant_remarks="None",
    )

    call = _FakeAsyncClient.calls[0]
    assert call["headers"]["Signed-Fields"] == (
        "vendor,order_id,buyer_email,buyer_name,buyer_phone,amount,currency,"
        "buyer_remarks,merchant_remarks,no_of_items"
    )


@pytest.mark.asyncio
async def test_gateway_styling_and_expiry_fields_appended_after_no_of_items():
    await _client().create_order_minimal(
        order_id="ORD-1",
        buyer_email="john@example.com",
        buyer_name="John Joh",
        buyer_phone="255682000000",
        amount="8000",
        no_of_items=1,
        header_colour="#000000",
        link_colour="#111111",
        button_colour="#222222",
        expiry=30,
    )

    call = _FakeAsyncClient.calls[0]
    assert list(call["json"].keys()) == [
        "vendor",
        "order_id",
        "buyer_email",
        "buyer_name",
        "buyer_phone",
        "amount",
        "currency",
        "no_of_items",
        "header_colour",
        "link_colour",
        "button_colour",
        "expiry",
    ]
    assert call["json"]["expiry"] == "30"
    assert call["headers"]["Signed-Fields"].endswith("no_of_items,header_colour,link_colour,button_colour,expiry")


@pytest.mark.asyncio
async def test_gateway_styling_fields_omitted_when_absent():
    await _client().create_order_minimal(
        order_id="ORD-1",
        buyer_email="john@example.com",
        buyer_name="John Joh",
        buyer_phone="255682000000",
        amount="8000",
        no_of_items=1,
    )

    call = _FakeAsyncClient.calls[0]
    for field in ("header_colour", "link_colour", "button_colour", "expiry"):
        assert field not in call["json"]
        assert field not in call["headers"]["Signed-Fields"]


# --- official-shell diagnostic variant (never used by application code) --------------


@pytest.mark.asyncio
async def test_official_shell_variant_signs_the_literal_shell_field_list():
    await _client().create_order_minimal(
        order_id="ORD-1",
        buyer_email="john@example.com",
        buyer_name="John Joh",
        buyer_phone="255682000000",
        amount="8000",
        no_of_items=1,
        webhook="https://example.com/webhook",
        buyer_remarks="None",
        merchant_remarks="None",
        signed_fields_variant="official-shell",
    )

    call = _FakeAsyncClient.calls[0]
    assert call["headers"]["Signed-Fields"] == (
        "vendor,order_id,buyer_email,buyer_name,buyer_user_id,buyer_phone,amount,currency,"
        "payment_methods,webhook,payer_remarks,merchant_remarks,order_items"
    )


@pytest.mark.asyncio
async def test_official_shell_variant_never_changes_the_actual_json_body():
    """The whole point of this diagnostic variant is a body/signature
    mismatch — the body itself must still be exactly what production
    would send, using the real (not shell) field names."""
    await _client().create_order_minimal(
        order_id="ORD-1",
        buyer_email="john@example.com",
        buyer_name="John Joh",
        buyer_phone="255682000000",
        amount="8000",
        no_of_items=1,
        buyer_remarks="None",
        signed_fields_variant="official-shell",
    )

    call = _FakeAsyncClient.calls[0]
    assert "buyer_user_id" not in call["json"]
    assert "payment_methods" not in call["json"]
    assert "payer_remarks" not in call["json"]
    assert "order_items" not in call["json"]
    assert call["json"]["buyer_remarks"] == "None"
    assert call["json"]["no_of_items"] == "1"


@pytest.mark.asyncio
async def test_unknown_signed_fields_variant_raises():
    with pytest.raises(ValueError):
        await _client().create_order_minimal(
            order_id="ORD-1",
            buyer_email="john@example.com",
            buyer_name="John Joh",
            buyer_phone="255682000000",
            amount="8000",
            no_of_items=1,
            signed_fields_variant="something-else",
        )


@pytest.mark.asyncio
async def test_create_order_minimal_base64_encodes_urls_only():
    await _client().create_order_minimal(
        order_id="ORD-1",
        buyer_email="john@example.com",
        buyer_name="John Joh",
        buyer_phone="255682000000",
        amount="8000",
        no_of_items=1,
        webhook="https://example.com/webhook",
    )

    call = _FakeAsyncClient.calls[0]
    assert call["json"]["webhook"] != "https://example.com/webhook"  # base64-encoded, not raw
    assert call["json"]["buyer_email"] == "john@example.com"  # never encoded


@pytest.mark.asyncio
async def test_create_order_minimal_never_sends_api_secret_or_key_material():
    await _client().create_order_minimal(
        order_id="ORD-1",
        buyer_email="john@example.com",
        buyer_name="John Joh",
        buyer_phone="255682000000",
        amount="8000",
        no_of_items=1,
    )

    call = _FakeAsyncClient.calls[0]
    assert "test-secret" not in json.dumps(call["json"])
    assert "test-secret" not in json.dumps(call["headers"])


# --- non-2xx handling -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_2xx_response_raises_selcom_checkout_error():
    _FakeAsyncClient._next_response = _FakeResponse(422, {"message": "Validation failed."})

    with pytest.raises(SelcomAPIError) as exc_info:
        await _client().create_order_minimal(
            order_id="ORD-1",
            buyer_email="john@example.com",
            buyer_name="John Joh",
            buyer_phone="255682000000",
            amount="8000",
            no_of_items=1,
        )

    assert exc_info.value.provider_status_code == 422
