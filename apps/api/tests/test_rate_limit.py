"""app/core/rate_limit.py — the in-memory fixed-window limiter applied to
abuse-prone endpoints (forgot-password, public pay, webhooks, withdrawal
request/approval, merchant API key creation, collection creation). Unit
coverage of the limiter itself; individual router test files
(test_disbursements.py, test_collections_api.py, test_merchant_portal.py)
each carry one wiring test proving a specific endpoint is actually gated,
not just that the shared mechanism works in isolation.
"""

import time
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.errors import register_exception_handlers
from app.core.rate_limit import RateLimitExceededError, _InMemoryRateLimiter, rate_limit


def test_allows_requests_under_the_limit():
    limiter = _InMemoryRateLimiter()
    for _ in range(5):
        limiter.check("bucket", limit=5, window_seconds=60)  # must not raise


def test_blocks_the_request_that_exceeds_the_limit():
    limiter = _InMemoryRateLimiter()
    for _ in range(5):
        limiter.check("bucket", limit=5, window_seconds=60)

    with pytest.raises(RateLimitExceededError):
        limiter.check("bucket", limit=5, window_seconds=60)


def test_buckets_are_independent_by_key():
    limiter = _InMemoryRateLimiter()
    for _ in range(5):
        limiter.check("bucket-a", limit=5, window_seconds=60)

    limiter.check("bucket-b", limit=5, window_seconds=60)  # a different key, unaffected


def test_old_hits_expire_out_of_the_window():
    limiter = _InMemoryRateLimiter()
    for _ in range(3):
        limiter.check("bucket", limit=3, window_seconds=0.05)

    time.sleep(0.1)

    limiter.check("bucket", limit=3, window_seconds=0.05)  # window has rolled — must not raise


def test_rate_limit_exceeded_error_is_429():
    err = RateLimitExceededError("test")
    assert err.status_code == 429
    assert err.code == "rate_limited"


def test_rate_limit_dependency_blocks_after_limit_hit_via_real_request():
    """End-to-end through a real FastAPI Depends(...) wiring + TestClient,
    not just the limiter class directly — proves the exact pattern every
    router uses actually works, using a throwaway app/route so this test
    doesn't depend on any real endpoint's own setup/fixtures. A fresh
    scope per test run avoids collisions with any other test that
    happens to exercise the same in-memory limiter singleton."""
    app = FastAPI()
    register_exception_handlers(app)
    scope = f"test-{time.monotonic()}"

    @app.get("/throwaway")
    def _throwaway(_rl: Annotated[None, Depends(rate_limit(scope=scope, limit=2, window_seconds=60))]):
        return {"ok": True}

    client = TestClient(app)

    assert client.get("/throwaway").status_code == 200
    assert client.get("/throwaway").status_code == 200

    third = client.get("/throwaway")
    assert third.status_code == 429
    assert third.json()["error"]["code"] == "rate_limited"
