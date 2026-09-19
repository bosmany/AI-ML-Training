"""Domain errors + the JSON error envelope (reference solution).

Every error the API returns has the same shape::

    {"error": {"code": "not_found", "message": "Candidate 7 not found", "details": null}}
"""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("lab")


# --------------------------------------------------------------------- scaffold (provided)
class AppError(Exception):
    """Base class for errors the service layer raises on purpose."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, *, headers: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.headers = headers


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class AuthenticationError(AppError):
    """Missing / invalid / expired credentials. Responses carry ``WWW-Authenticate: Bearer``."""

    status_code = 401
    code = "unauthorized"

    def __init__(self, message: str = "Not authenticated") -> None:
        super().__init__(message, headers={"WWW-Authenticate": "Bearer"})


class PermissionDeniedError(AppError):
    status_code = 403
    code = "forbidden"


def error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    """The one and only error envelope."""
    return {"error": {"code": code, "message": message, "details": details}}


# --------------------------------------------------------------------- your work
def register_exception_handlers(app: FastAPI) -> None:
    """Attach handlers so that EVERY error uses the envelope from ``error_body``."""

    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            error_body(exc.code, exc.message), status_code=exc.status_code, headers=exc.headers
        )

    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Catches routing errors too (unknown path -> 404, wrong verb -> 405).
        code = HTTPStatus(exc.status_code).phrase.lower().replace(" ", "_")
        return JSONResponse(
            error_body(code, str(exc.detail)),
            status_code=exc.status_code,
            headers=getattr(exc, "headers", None),
        )

    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Do not pass exc.errors() straight through: "ctx"/"input" may not be JSON serialisable.
        details = [
            {"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]} for err in exc.errors()
        ]
        return JSONResponse(
            error_body("validation_error", "Request validation failed", details), status_code=422
        )

    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        # Never leak str(exc) to the client.
        return JSONResponse(error_body("internal_error", "Internal server error"), status_code=500)

    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_unexpected)
