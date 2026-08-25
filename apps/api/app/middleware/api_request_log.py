"""Logs one row per API-key-authenticated HTTP request to
api_request_logs — the "API Logs" merchant/Super Admin views ask for.
Only requests that actually resolved a valid API key are logged here
(request.state.api_key_context, set by
app.auth.dependencies.verify_api_key on success): an invalid/unknown key
has no merchant to attribute a log row to, and isn't logged by this
middleware — see that dependency's own docstring for the one exception
(an IP-allowlist rejection, which *does* know the merchant by the time
it's rejected, and logs itself explicitly instead of relying on this
middleware).

Best-effort throughout: a logging failure must never break the real
request/response it's describing.
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.database.session import get_supabase_admin


class ApiRequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.monotonic()
        response = await call_next(request)

        context = getattr(request.state, "api_key_context", None)
        if context is not None:
            duration_ms = int((time.monotonic() - start) * 1000)
            ip = getattr(request.state, "client_ip", None)
            try:
                get_supabase_admin().table("api_request_logs").insert(
                    {
                        "merchant_id": str(context.merchant_id),
                        "api_key_id": str(context.id),
                        "environment": context.environment,
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "ip_address": ip,
                        "duration_ms": duration_ms,
                    }
                ).execute()
            except Exception:  # noqa: BLE001, S110
                pass

        return response
