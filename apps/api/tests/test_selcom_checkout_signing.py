"""app/services/selcom_checkout/signer.py — HS256 (HMAC-SHA256) and RS256
(RSA-SHA256) request signing against the scheme confirmed at
https://developers.selcommobile.com/ (fetched 2026-08-22). Distinct
product/signing scheme from app/services/selcom_business/ (see
tests/test_selcom_business_client.py) and from the older, unconfirmed
app/services/selcom/ placeholder (see tests/test_selcom_signature.py).
"""

import base64
import hashlib
import hmac

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.services.selcom_checkout.errors import SelcomCheckoutMisconfiguredError
from app.services.selcom_checkout.signer import (
    build_auth_headers,
    build_signing_string,
    sign_request,
)


def _generate_test_private_key_base64() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return base64.b64encode(pem).decode("ascii"), key


# --- signing string ---------------------------------------------------------------


def test_signing_string_puts_timestamp_first_then_fields_in_order():
    fields = {"utilitycode": "LUKU", "utilityref": "654944949", "vendor": "66546846845", "amount": "1234"}

    signing_string = build_signing_string(timestamp="2019-02-26T09:30:46+03:00", fields=fields)

    assert signing_string == (
        "timestamp=2019-02-26T09:30:46+03:00"
        "&utilitycode=LUKU&utilityref=654944949&vendor=66546846845&amount=1234"
    )


def test_signing_string_matches_the_documented_example():
    # Directly from https://developers.selcommobile.com/'s own example.
    fields = {
        "utilitycode": "LUKU",
        "utilityref": "654944949",
        "vendor": "66546846845",
        "pin": "48585",
        "transid": "T001",
        "amount": "1234",
    }

    signing_string = build_signing_string(timestamp="2019-02-26T09:30:46+03:00", fields=fields)

    assert signing_string == (
        "timestamp=2019-02-26T09:30:46+03:00&utilitycode=LUKU&utilityref=654944949"
        "&vendor=66546846845&pin=48585&transid=T001&amount=1234"
    )


# --- HS256 (HMAC-SHA256) signing ---------------------------------------------------


def test_hs256_digest_matches_manually_computed_hmac_sha256():
    fields = {"orderId": "ORD-1", "amount": "1000"}
    timestamp = "2026-08-22T12:00:00.000Z"
    api_secret = "test-secret"

    ts, digest, signed_fields = sign_request(
        fields, digest_method="HS256", api_secret=api_secret, timestamp=timestamp
    )

    expected_signing_string = "timestamp=2026-08-22T12:00:00.000Z&orderId=ORD-1&amount=1000"
    expected_digest = base64.b64encode(
        hmac.new(api_secret.encode("utf-8"), expected_signing_string.encode("utf-8"), hashlib.sha256).digest()
    ).decode("ascii")

    assert ts == timestamp
    assert digest == expected_digest
    assert signed_fields == "orderId,amount"


def test_hs256_signing_is_deterministic_for_a_fixed_timestamp():
    fields = {"orderId": "ORD-1", "amount": "1000"}
    ts = "2026-08-22T12:00:00.000Z"

    _, digest_a, _ = sign_request(fields, digest_method="HS256", api_secret="s3cr3t", timestamp=ts)
    _, digest_b, _ = sign_request(fields, digest_method="HS256", api_secret="s3cr3t", timestamp=ts)

    assert digest_a == digest_b


def test_hs256_digest_changes_when_a_field_value_changes():
    ts = "2026-08-22T12:00:00.000Z"

    _, digest_a, _ = sign_request({"amount": "1000"}, digest_method="HS256", api_secret="s3cr3t", timestamp=ts)
    _, digest_b, _ = sign_request({"amount": "2000"}, digest_method="HS256", api_secret="s3cr3t", timestamp=ts)

    assert digest_a != digest_b


def test_hs256_digest_changes_when_the_secret_changes():
    fields = {"amount": "1000"}
    ts = "2026-08-22T12:00:00.000Z"

    _, digest_a, _ = sign_request(fields, digest_method="HS256", api_secret="secret-a", timestamp=ts)
    _, digest_b, _ = sign_request(fields, digest_method="HS256", api_secret="secret-b", timestamp=ts)

    assert digest_a != digest_b


def test_hs256_without_api_secret_raises_misconfigured():
    with pytest.raises(SelcomCheckoutMisconfiguredError):
        sign_request({"amount": "1000"}, digest_method="HS256", api_secret="")


def test_build_timestamp_returns_utc_z_suffixed_iso8601():
    from app.services.selcom_checkout.signer import build_timestamp

    ts = build_timestamp()
    assert ts.endswith("Z")
    assert "T" in ts
    assert len(ts) == len("2026-08-22T12:00:00.000Z")


def test_build_timestamp_php_style_matches_the_documented_shape():
    from app.services.selcom_checkout.signer import build_timestamp_php_style

    ts = build_timestamp_php_style()
    # "yyyy-dd-mm H:i:s" per the Create Order - Minimal shell headers —
    # not ISO-8601: no "T", no "Z", no timezone offset.
    assert "T" not in ts
    assert not ts.endswith("Z")
    assert len(ts) == len("2026-22-08 12:00:00")
    date_part, time_part = ts.split(" ")
    assert len(date_part.split("-")) == 3
    assert len(time_part.split(":")) == 3


# --- RS256 (RSA-SHA256) signing -----------------------------------------------------


def test_rs256_digest_verifies_against_the_matching_public_key():
    private_key_base64, private_key = _generate_test_private_key_base64()
    fields = {"orderId": "ORD-1", "amount": "1000"}
    timestamp = "2026-08-22T12:00:00.000Z"

    ts, digest, signed_fields = sign_request(
        fields, digest_method="RS256", private_key_base64=private_key_base64, timestamp=timestamp
    )

    signing_string = "timestamp=2026-08-22T12:00:00.000Z&orderId=ORD-1&amount=1000"
    public_key = private_key.public_key()
    # Raises if the signature doesn't verify — the assertion is that this doesn't raise.
    public_key.verify(base64.b64decode(digest), signing_string.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())

    assert ts == timestamp
    assert signed_fields == "orderId,amount"


def test_rs256_without_private_key_raises_misconfigured():
    with pytest.raises(SelcomCheckoutMisconfiguredError):
        sign_request({"amount": "1000"}, digest_method="RS256", private_key_base64="")


def test_rs256_with_a_non_rsa_key_raises_misconfigured():
    from cryptography.hazmat.primitives.asymmetric import ed25519

    key = ed25519.Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    non_rsa_key_base64 = base64.b64encode(pem).decode("ascii")

    with pytest.raises(SelcomCheckoutMisconfiguredError):
        sign_request({"amount": "1000"}, digest_method="RS256", private_key_base64=non_rsa_key_base64)


# --- unsupported digest method ------------------------------------------------------


def test_unsupported_digest_method_raises_misconfigured():
    with pytest.raises(SelcomCheckoutMisconfiguredError):
        sign_request({"amount": "1000"}, digest_method="MD5", api_secret="s3cr3t")


# --- full header set -----------------------------------------------------------------


def test_build_auth_headers_produces_the_documented_header_shape():
    fields = {"orderId": "ORD-1", "amount": "1000"}

    headers = build_auth_headers(
        fields,
        api_key="my-api-key",
        digest_method="HS256",
        api_secret="s3cr3t",
        timestamp="2026-08-22T12:00:00.000Z",
    )

    expected_authorization = "SELCOM " + base64.b64encode(b"my-api-key").decode("ascii")
    assert headers["Authorization"] == expected_authorization
    assert headers["Digest-Method"] == "HS256"
    assert headers["Timestamp"] == "2026-08-22T12:00:00.000Z"
    assert headers["Signed-Fields"] == "orderId,amount"
    assert headers["Accept"] == "application/json"
    assert headers["Content-Type"] == "application/json"
    assert headers.get("Digest")
    # The secret itself must never appear anywhere in the headers.
    assert "s3cr3t" not in headers.values()


def test_build_auth_headers_without_api_key_raises_misconfigured():
    with pytest.raises(SelcomCheckoutMisconfiguredError):
        build_auth_headers({"amount": "1000"}, api_key="", digest_method="HS256", api_secret="s3cr3t")
