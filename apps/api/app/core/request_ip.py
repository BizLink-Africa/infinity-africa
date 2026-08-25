"""The real client IP for a request that may have passed through a proxy
(Railway's edge, in production) — used for API key last_used_ip,
api_request_logs, and IP allowlist enforcement. `X-Forwarded-For` can
carry a comma-separated chain (client, proxy1, proxy2, ...); the first
entry is the original client, added by the first proxy the request hit.
"""

from fastapi import Request


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else None
