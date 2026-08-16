"""Pure unit tests for app/services/selcom/signature.py — the outbound
request-signing helper used only when SELCOM_MODE=live (no live Selcom call
happens in these tests; see app/services/selcom/live_client.py for where
this signing scheme's caveats are explained)."""

import hashlib
import hmac

from app.services.selcom.signature import build_timestamp, compute_digest, sign_request


def test_compute_digest_is_hmac_sha256_of_the_exact_payload():
    payload = b'{"amount": "1000.00"}'
    digest = compute_digest(payload, api_secret="s3cr3t")

    expected = hmac.new(b"s3cr3t", payload, hashlib.sha256).hexdigest()
    assert digest == expected


def test_compute_digest_changes_with_payload_or_secret():
    payload = b'{"amount": "1000.00"}'
    base = compute_digest(payload, api_secret="s3cr3t")

    assert compute_digest(payload, api_secret="different") != base
    assert compute_digest(b'{"amount": "2000.00"}', api_secret="s3cr3t") != base


def test_sign_request_returns_expected_headers_without_leaking_the_secret():
    payload = b'{"order_id": "COL-1"}'
    headers = sign_request(payload, api_key="key123", api_secret="s3cr3t", vendor_id="VENDOR-1")

    assert headers["Authorization"] == "SELCOM key123"
    assert headers["Vendor"] == "VENDOR-1"
    assert headers["Digest-Method"] == "HS256"
    assert headers["Digest"] == compute_digest(payload, api_secret="s3cr3t")
    assert "s3cr3t" not in headers.values()
    assert headers["Timestamp"]


def test_sign_request_uses_the_given_timestamp_when_provided():
    payload = b"{}"
    headers = sign_request(
        payload, api_key="key123", api_secret="s3cr3t", vendor_id="VENDOR-1", timestamp="2026-08-16T00:00:00Z"
    )

    assert headers["Timestamp"] == "2026-08-16T00:00:00Z"


def test_build_timestamp_is_iso8601_utc_with_z_suffix():
    ts = build_timestamp()

    assert ts.endswith("Z")
    assert "T" in ts
    assert len(ts) == 20  # YYYY-MM-DDTHH:MM:SSZ
