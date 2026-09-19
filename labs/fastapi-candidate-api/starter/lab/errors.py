"""Domain errors + the JSON error envelope (starter).

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
    """Attach handlers so that EVERY error uses the envelope from ``error_body``.

    TODO 1: ``AppError``               -> status/code/message from the exception (+ ``exc.headers``).
    TODO 2: ``StarletteHTTPException`` -> also fires for routing errors (unknown path 404, wrong verb 405).
            Derive ``code`` from the status phrase: 404 -> "not_found", 405 -> "method_not_allowed".
            Keep ``exc.headers``.
    TODO 3: ``RequestValidationError`` -> 422, code "validation_error", ``details`` = list of
            {"loc": [...], "msg": ..., "type": ...}. Build it by hand: ``exc.errors()`` may contain
            objects (e.g. a ValueError under "ctx") that ``JSONResponse`` cannot serialise.
    TODO 4: ``Exception``              -> 500, code "internal_error", generic message. Log the real
            error with ``logger.exception`` but never send it to the client.

    Register them with ``app.add_exception_handler(...)``. This function is called by ``create_app``
    BEFORE the first request - see ``lab/app.py`` for why that ordering matters.
    """
    raise NotImplementedError("TODO: register the four exception handlers")
