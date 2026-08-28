"""A minimal, dependency-free rate limiter for abuse-prone endpoints
(forgot-password, public payment attempts, webhooks, withdrawal
request/approval, merchant API key creation) — see
docs/MVP_LAUNCH_CHECKLIST.md, "Rate limiting" for the full endpoint list
and known limitation below.

In-memory, fixed-window, per-process. Deliberately simple rather than
pulling in a new dependency (no rate-limiting package existed anywhere in
this codebase before this) — correct for this deployment's current
single-replica Railway setup (confirmed 2026-08-28), but **does not
share state across replicas**: if this API is ever scaled to more than
one instance without a shared store (Redis, etc.), each replica enforces
its own independent limit rather than one combined limit. Revisit with a
Redis-backed limiter (or a proxy/edge-level limiter — Railway/Cloudflare)
before scaling horizontally.
"""

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import Request

from app.core.errors import APIError
from app.core.request_ip import client_ip


class RateLimitExceededError(APIError):
    status_code = 429
    code = "rate_limited"


class _InMemoryRateLimiter:
    """Fixed-window counter per (scope, key) — `key` is normally the
    caller's IP, so each scope's limit applies per-IP, independent of
    every other scope. Thread-safe: uvicorn can run a sync dependency
    function in a worker thread, and multiple requests can race here
    concurrently even on a single process."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, bucket_key: str, *, limit: int, window_seconds: float) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[bucket_key]
            while hits and now - hits[0] > window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                raise RateLimitExceededError("Too many requests. Please try again in a few minutes.")
            hits.append(now)


_limiter = _InMemoryRateLimiter()


def rate_limit(*, scope: str, limit: int, window_seconds: float):
    """Returns a FastAPI dependency: `Depends(rate_limit(scope="...",
    limit=N, window_seconds=W))`. `scope` namespaces the bucket so the
    same caller IP is tracked independently per endpoint/purpose — hitting
    the limit on one scope never affects another. Keyed by IP (via
    app.core.request_ip.client_ip); a request with no resolvable client IP
    at all (host missing, e.g. some test clients) falls back to a shared
    "unknown" bucket rather than skipping the limit entirely."""

    def _dependency(request: Request) -> None:
        ip = client_ip(request) or "unknown"
        _limiter.check(f"{scope}:{ip}", limit=limit, window_seconds=window_seconds)

    return _dependency
