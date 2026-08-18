"""Application error types + the exception handlers that turn them (and
anything else unhandled) into the standard {"success": false, "error": {...}}
envelope, registered onto the FastAPI app in app.main.
"""

import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.common import ErrorDetail, ErrorResponse

logger = logging.getLogger("infinity.api")


class APIError(Exception):
    """Base class for application errors. Raise a subclass (or this
    directly) anywhere in a router/service to get a well-formed error
    response instead of a bare 500."""

    status_code = status.HTTP_400_BAD_REQUEST
    code = "bad_request"

    def __init__(self, message: str, *, details: list | dict | None = None):
        self.message = message
        self.details = details
        super().__init__(message)


class NotFoundError(APIError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(APIError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class ValidationAPIError(APIError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "validation_error"


class IdempotencyKeyReusedError(ConflictError):
    code = "idempotency_key_reused"


class InsufficientBalanceError(ConflictError):
    code = "insufficient_balance"


class WithdrawalRestrictedError(ConflictError):
    code = "withdrawal_restricted"


class SelcomAPIError(APIError):
    """Selcom returned a non-2xx response, an unparseable body, or the
    request failed outright (timeout/connection error). 502, not 409/500 —
    this is an upstream provider failure, not a conflict in our own data or
    a bug in our own code. See app/services/selcom/client.py.

    `provider_status_code` (when known — a live HTTP error, not a
    connection failure) is Selcom's own response status, e.g. 403 for an
    IP-whitelist rejection — deliberately a different attribute from
    `status_code`, which is always 502 (this app's own response code to
    *its* caller, unrelated to what Selcom returned).

    `is_ip_whitelist_error` is the specific "Railway's outbound IP isn't
    whitelisted with Selcom yet" signal (HTTP 403 and/or Selcom's own error
    code 611 in the response body, per
    app/services/selcom_business/live_client.py) — deliberately its own flag
    rather than callers comparing `provider_status_code == 403` themselves,
    since a bare 403 alone is ambiguous (could also mean a bad API key)."""

    status_code = status.HTTP_502_BAD_GATEWAY
    code = "selcom_api_error"

    def __init__(
        self,
        message: str,
        *,
        details: list | dict | None = None,
        provider_status_code: int | None = None,
        is_ip_whitelist_error: bool = False,
    ):
        super().__init__(message, details=details)
        self.provider_status_code = provider_status_code
        self.is_ip_whitelist_error = is_ip_whitelist_error


def _error_content(code: str, message: str, details=None) -> dict:
    return ErrorResponse(error=ErrorDetail(code=code, message=message, details=details)).model_dump(
        mode="json"
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError):
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_content(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        # exc.errors() can embed a raw exception object in `ctx` (e.g. a
        # field_validator that raises ValueError) — jsonable_encoder is what
        # actually makes that safe to serialize, not just str()-ing it.
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_content("validation_error", "Invalid request", jsonable_encoder(exc.errors())),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        code = {
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            409: "conflict",
        }.get(exc.status_code, "http_error")
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_content(code, str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_content("internal_error", "An unexpected error occurred"),
        )
