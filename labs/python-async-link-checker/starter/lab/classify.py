"""Turning status codes and exceptions into ``Status`` values, and the retry delay schedule."""
from __future__ import annotations

import socket  # noqa: F401

import httpx  # noqa: F401

from .models import Status


def classify_status(code: int) -> Status:
    """2xx -> OK, 4xx -> CLIENT_ERROR, 5xx -> SERVER_ERROR; anything else (1xx, a 3xx we could not follow) ->
    CLIENT_ERROR.

    TODO: implement.
    """
    raise NotImplementedError


def classify_exception(exc: BaseException) -> tuple[Status, str]:
    """Map a request failure to ``(status, message)``.

    TODO:
    - ``httpx.TimeoutException`` and ``TimeoutError`` (what ``asyncio.timeout()`` raises) -> TIMEOUT.
      Check this FIRST: ``httpx.ConnectTimeout`` is also a ``TransportError``.
    - other ``httpx.TransportError`` / ``OSError``: if a ``socket.gaierror`` appears anywhere in the ``__cause__`` /
      ``__context__`` chain -> DNS_ERROR, else CONNECTION_ERROR
    - the message is ``"<ExceptionName>: <text>"``
    - anything else is a bug in the caller, not a broken link: re-raise it (``raise exc``)
    """
    raise NotImplementedError


def backoff_delay(attempt: int, base: float, cap: float = 30.0) -> float:
    """Seconds to wait before retry number ``attempt`` (0 = the first retry).

    TODO: ``min(cap, base * 2 ** attempt)`` -> with base 0.5: 0.5, 1.0, 2.0, 4.0 ...
    """
    raise NotImplementedError
