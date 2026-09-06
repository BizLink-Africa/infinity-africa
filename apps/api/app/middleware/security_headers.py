"""Adds standard defensive HTTP response headers to every response this API
sends — MVP security-hardening pass, see docs/MVP_LAUNCH_CHECKLIST.md's
"Security headers" checklist.

This API is a pure JSON backend, deliberately consumed cross-origin by
apps/web over CORS (app.main's CORSMiddleware already gates *which*
origins may do that) — two headers a browsable HTML site would normally
also set are intentionally left out here:

  - Cross-Origin-Resource-Policy: setting this to "same-origin" would block
    the browser from delivering this API's own responses to apps/web's
    cross-origin fetch() calls even though CORS explicitly permits them —
    the opposite of "safe" for this specific app. apps/web's own frontend
    (next.config.ts) sets CORP: same-origin instead, where it's actually
    correct (nothing else is meant to load its JS/CSS/images cross-origin).
  - Cross-Origin-Opener-Policy: meaningless for a JSON API with no window/
    opener relationship to isolate — it only matters for a page that opens
    or is opened by another browsing context.

Content-Security-Policy here is a defense-in-depth minimum for the rare
response that *is* HTML (an unhandled-error fallback page, a future
redirect) — `default-src 'none'` never needs relaxing for JSON responses,
which don't execute a CSP at all. Swagger UI (/docs, /redoc) needs its own
inline scripts/styles and an external CDN, so this middleware skips those
specific paths entirely rather than weakening the policy for every route;
they're already disabled outright in production (see app.main's
_docs_enabled) where this would matter most.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_DOCS_PATHS = {"/docs", "/redoc", "/openapi.json"}

_HEADERS = {
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
}
_CSP_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        for key, value in _HEADERS.items():
            response.headers.setdefault(key, value)
        if request.url.path not in _DOCS_PATHS:
            for key, value in _CSP_HEADERS.items():
                response.headers.setdefault(key, value)
        return response
