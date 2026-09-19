"""App factory, middleware, and the consistent error envelope."""

from __future__ import annotations

import pytest
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from lab.app import create_app
from lab.errors import AppError


def test_health_endpoint_reports_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_timing_header_is_present_and_numeric_on_success_and_on_errors(client):
    for path in ("/health", "/does-not-exist"):
        response = client.get(path)
        header = response.headers.get("X-Process-Time-Ms")
        assert header is not None, f"GET {path} ({response.status_code}) has no X-Process-Time-Ms header"
        assert float(header) >= 0, f"header should be a non-negative number of milliseconds, got {header!r}"


def test_factory_registers_handlers_and_middleware_before_any_request(settings):
    app = create_app(settings)
    assert app.middleware_stack is None, "sanity: no request has been served yet"

    handlers = app.exception_handlers
    assert AppError in handlers, "AppError handler must be registered inside the factory"
    assert Exception in handlers, "catch-all Exception handler (500 envelope) must be registered"
    assert handlers[StarletteHTTPException] is not http_exception_handler, (
        "the default HTTPException handler is still in place - override it (404/405 must use the envelope)"
    )
    assert handlers[RequestValidationError] is not request_validation_exception_handler, (
        "the default 422 handler is still in place - override it to use the envelope"
    )
    assert len(app.user_middleware) >= 1, "the timing middleware must be added inside the factory"

    other = create_app(settings)
    assert other is not app
    assert other.state.events is not app.state.events, "each app instance needs its own event log"


def test_handlers_and_middleware_added_after_the_first_request_are_ignored(settings):
    """Why the factory matters: Starlette freezes its middleware stack on the first request."""

    class LateError(Exception):
        pass

    app = create_app(settings)

    def raise_late() -> None:
        raise LateError("boom")

    app.add_api_route("/late", raise_late)  # routes may be added late; handlers/middleware may not
    client = TestClient(app, raise_server_exceptions=False)
    assert client.get("/health").status_code == 200  # first request builds the stack

    app.add_exception_handler(
        LateError, lambda request, exc: JSONResponse({"custom": True}, status_code=418)
    )
    response = client.get("/late")
    assert response.status_code == 500, "a handler registered after the first request must NOT be used"
    assert response.json()["error"]["code"] == "internal_error"

    with pytest.raises(RuntimeError):
        app.add_middleware(type("Late", (), {}))


def test_unexpected_exception_becomes_a_500_envelope_without_leaking_details(settings):
    app = create_app(settings)

    def explode() -> None:
        raise RuntimeError("password=hunter2 in the connection string")

    app.add_api_route("/boom", explode)  # before the first request, so this is fine
    response = TestClient(app, raise_server_exceptions=False).get("/boom")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert "hunter2" not in response.text, "internal exception text must never reach the client"


def test_framework_raised_errors_use_the_same_envelope(client):
    not_found = client.get("/no/such/route")
    assert not_found.status_code == 404
    assert not_found.json()["error"]["code"] == "not_found"

    wrong_verb = client.post("/health")
    assert wrong_verb.status_code == 405
    assert wrong_verb.json()["error"]["code"] == "method_not_allowed"

    invalid = client.get("/candidates", params={"page": "zero"})
    assert invalid.status_code == 422
    error = invalid.json()["error"]
    assert error["code"] == "validation_error"
    assert isinstance(error["details"], list) and error["details"], "details should list each problem"
    assert {"loc", "msg"} <= set(error["details"][0]), "each detail needs 'loc' and 'msg'"
    assert error["details"][0]["loc"][-1] == "page"
