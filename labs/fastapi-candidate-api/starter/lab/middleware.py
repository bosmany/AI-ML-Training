"""Request-timing middleware (starter)."""

from __future__ import annotations

from fastapi import FastAPI


def add_timing_middleware(app: FastAPI) -> None:
    """Add an HTTP middleware that sets ``X-Process-Time-Ms`` on every response.

    TODO: use ``@app.middleware("http")`` (or a pure ASGI middleware). Measure with
    ``time.perf_counter()`` around ``await call_next(request)`` and set the header to the elapsed
    milliseconds as a plain decimal string, e.g. ``"3.142"``. It must also be present on error
    responses (404, 401, 422 ...). Called by ``create_app`` before the first request.
    """
    raise NotImplementedError("TODO: add the timing middleware")
