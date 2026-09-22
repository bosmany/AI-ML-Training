"""Turning status codes and exceptions into ``Status`` values, and the retry delay schedule."""
from __future__ import annotations

import socket

import httpx

from .models import Status


def classify_status(code: int) -> Status:
    """2xx -> OK, 4xx -> CLIENT_ERROR, 5xx -> SERVER_ERROR; anything else (1xx, a 3xx that could not be
    followed) -> CLIENT_ERROR."""
    if 200 <= code < 300:
        return Status.OK
    if 500 <= code < 600:
        return Status.SERVER_ERROR
    return Status.CLIENT_ERROR


def _caused_by(exc: BaseException, kind: type[BaseException]) -> bool:
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        if isinstance(current, kind):
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return False


def classify_exception(exc: BaseException) -> tuple[Status, str]:
    """Map a request failure to ``(status, message)``.

    Timeouts (httpx timeouts and ``TimeoutError``) -> TIMEOUT; a failed name lookup (``socket.gaierror`` anywhere in
    the cause chain) -> DNS_ERROR; other transport/OS errors -> CONNECTION_ERROR. Anything else is a bug in the
    caller and is re-raised unchanged.
    """
    message = f"{type(exc).__name__}: {exc}"
    if isinstance(exc, httpx.TimeoutException | TimeoutError):
        return Status.TIMEOUT, message
    if isinstance(exc, httpx.TransportError | OSError):
        if _caused_by(exc, socket.gaierror):
            return Status.DNS_ERROR, message
        return Status.CONNECTION_ERROR, message
    raise exc


def backoff_delay(attempt: int, base: float, cap: float = 30.0) -> float:
    """Seconds to wait before retry number ``attempt`` (0 = the first retry): ``min(cap, base * 2**attempt)``."""
    return min(cap, base * 2 ** attempt)
