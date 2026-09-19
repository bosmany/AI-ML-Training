"""Request-timing middleware (reference solution)."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response


def add_timing_middleware(app: FastAPI) -> None:
    """Add an HTTP middleware that sets ``X-Process-Time-Ms`` on every response."""

    @app.middleware("http")
    async def timing(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.3f}"
        return response
