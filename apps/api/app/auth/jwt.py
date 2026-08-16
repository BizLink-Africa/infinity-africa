"""Supabase Auth JWT verification.

A Supabase project signs access tokens one of two ways:

- Current: asymmetric signing keys (ES256/RS256), verified via the
  project's JWKS endpoint (SUPABASE_JWKS_URL) — no shared secret exists for
  these at all.
- Legacy: HS256 with a shared secret (SUPABASE_JWT_SECRET) — fully local
  verification, no network call. A project that has rotated to signing keys
  still keeps its old HS256 secret valid to verify tokens minted before the
  rotation, until they naturally expire. This is also what the test suite's
  fake tokens use (see tests/factories.py) — SUPABASE_JWKS_URL is never set
  in tests, so they always take this path.

Both are tried (JWKS first, when configured) so a token from either era
verifies correctly during a project's transition period.
"""

from functools import lru_cache

import jwt
from jwt import PyJWKClient

from app.config import get_settings


class InvalidTokenError(Exception):
    """Raised when a bearer token fails signature, audience, or expiry checks."""


@lru_cache
def _jwks_client(jwks_url: str) -> PyJWKClient:
    """Cached per URL — PyJWKClient itself caches fetched keys in memory and
    only re-fetches when it sees an unrecognized `kid`, so this avoids both
    re-creating the client and re-fetching the JWKS on every request."""
    return PyJWKClient(jwks_url)


def _decode_via_jwks(token: str, *, jwks_url: str, issuer: str) -> dict:
    signing_key = _jwks_client(jwks_url).get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["ES256", "RS256"],
        audience="authenticated",
        issuer=issuer or None,
        options={"verify_iss": bool(issuer)},
    )


def _decode_via_shared_secret(token: str, *, secret: str) -> dict:
    return jwt.decode(token, secret, algorithms=["HS256"], audience="authenticated")


def decode_access_token(token: str) -> dict:
    """Verify a Supabase access token and return its claims.

    Raises InvalidTokenError on any failure (bad signature, expired,
    wrong audience, or — when both verification methods are configured —
    both failing) — callers should treat this uniformly as "unauthenticated"
    rather than branching on the specific cause.
    """
    settings = get_settings()

    if not settings.supabase_jwks_url and not settings.supabase_jwt_secret:
        raise RuntimeError("Neither SUPABASE_JWKS_URL nor SUPABASE_JWT_SECRET is configured")

    errors: list[str] = []

    if settings.supabase_jwks_url:
        try:
            return _decode_via_jwks(
                token, jwks_url=settings.supabase_jwks_url, issuer=settings.supabase_jwt_issuer
            )
        except Exception as exc:  # noqa: BLE001 - PyJWKClient can raise network
            # errors, unknown-kid lookup failures, or ordinary PyJWTErrors
            # (wrong algorithm, bad signature) — any of them just means "try
            # the shared-secret path next," not "fail the request".
            errors.append(str(exc))

    if settings.supabase_jwt_secret:
        try:
            return _decode_via_shared_secret(token, secret=settings.supabase_jwt_secret)
        except jwt.PyJWTError as exc:
            errors.append(str(exc))

    raise InvalidTokenError("; ".join(errors) or "no JWT verification method succeeded")
