"""The async core: one URL, many URLs (gather + semaphore) and a depth-limited crawl."""
from __future__ import annotations

import asyncio
import time  # noqa: F401
from collections.abc import Awaitable, Callable, Collection
from dataclasses import replace  # noqa: F401
from urllib.parse import urljoin  # noqa: F401

import httpx

from .classify import backoff_delay, classify_exception, classify_status  # noqa: F401
from .models import CheckConfig, LinkResult, Report, Status
from .parsing import extract_links, is_same_host, normalize_url  # noqa: F401

Sleep = Callable[[float], Awaitable[None]]
ClientFactory = Callable[[CheckConfig], httpx.AsyncClient]

REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})
HEAD_FALLBACK_CODES = frozenset({405, 501})
RETRYABLE = frozenset({Status.TIMEOUT, Status.DNS_ERROR, Status.CONNECTION_ERROR, Status.SERVER_ERROR})


def make_timeout(config: CheckConfig) -> httpx.Timeout:
    """``httpx.Timeout`` using ``config.timeout`` for read/write/pool and ``config.connect_timeout`` for connect.

    TODO: ``httpx.Timeout(config.timeout, connect=config.connect_timeout)``.
    """
    raise NotImplementedError


def make_client(config: CheckConfig) -> httpx.AsyncClient:
    """The HTTP client shared by all requests of a run.

    TODO: ``httpx.AsyncClient(timeout=make_timeout(config), follow_redirects=False, ...)``. Redirects are followed by
    YOUR code so hops can be counted and capped. Do NOT set ``limits`` from ``config.concurrency``: the semaphore in
    ``check_urls`` is the mechanism the tests look for.
    """
    raise NotImplementedError


async def check_url(client: httpx.AsyncClient, url: str, config: CheckConfig, *, get_body: bool = False,
                    sleep: Sleep = asyncio.sleep) -> LinkResult:
    """Check ONE url, with retries. Network problems become results; they never raise.

    One *attempt* =
      - method HEAD (or GET when ``get_body``); if a HEAD is answered 405 or 501, repeat the SAME url with GET
        (that is part of the attempt, not a retry; a HEAD 404 is NOT retried with GET)
      - follow redirects yourself (301/302/303/307/308 with a ``Location``, resolved with ``urljoin``): after
        ``config.max_redirects`` hops another redirect gives ``Status.TOO_MANY_REDIRECTS``
      - the WHOLE attempt runs inside ``async with asyncio.timeout(config.timeout)``
      - final code: ``classify_status``; if >= 1 hop was followed and it is OK the status is ``REDIRECT``;
        ``final_url`` is set whenever a hop was followed (also when the final page is a 404)
      - ``body`` = ``response.text`` only when ``get_body`` and the response is OK and its content type contains "html"
      - ``latency`` = seconds spent on the last attempt (``time.monotonic()``)
    Exceptions (``except Exception``, so that ``CancelledError`` still propagates) -> ``classify_exception``.

    Retries: when the attempt's status is in ``RETRYABLE`` and fewer than ``config.retries`` retries were used, wait
    ``await sleep(backoff_delay(retry_number, config.backoff_base))`` (retry_number starts at 0) and try again.
    4xx is never retried; there is no sleep after the last attempt. ``LinkResult.attempts`` counts attempts made
    (``dataclasses.replace`` is handy).
    """
    raise NotImplementedError


async def check_urls(urls: Collection[str], config: CheckConfig, *, client: httpx.AsyncClient | None = None,
                     body_urls: Collection[str] = (), sleep: Sleep = asyncio.sleep,
                     on_result: Callable[[LinkResult], None] | None = None) -> list[LinkResult]:
    """Check every distinct URL concurrently, at most ``config.concurrency`` in flight.

    TODO:
    - ``config.validate()`` first (bad config must fail before any request)
    - de-duplicate ``urls`` keeping first-seen order (``dict.fromkeys``); results are returned in that order
    - if ``client`` is None create one with ``make_client`` and close it (``async with``)
    - one coroutine per URL wrapped in ``async with asyncio.Semaphore(config.concurrency)``, run with
      ``asyncio.gather``; URLs in ``body_urls`` use ``get_body=True``
    - call ``on_result(result)`` as each URL finishes (before the whole batch is done)
    - if anything goes wrong or the caller cancels, cancel the remaining tasks and wait for them, so no task is left
      pending
    """
    raise NotImplementedError


async def crawl(start_url: str, config: CheckConfig, *, depth: int = 1, client_factory: ClientFactory = make_client,
                report: Report | None = None, sleep: Sleep = asyncio.sleep) -> Report:
    """Check ``start_url`` and the links found on same-host pages up to ``depth`` page hops away.

    TODO (breadth-first, one ``check_urls`` call per level):
    - ``config.validate()``; ``depth < 0`` -> ``ValueError``; ``start = normalize_url(start_url)``; use the passed
      ``report`` or create ``Report(start_url=start)``; record the edge ``(None, start)``
    - level 0 is ``[start]``. Pages of a level ``< depth`` that are on the start host are fetched with GET
      (``body_urls``) and their links extracted with ``extract_links(result.body, final_url or url)``; everything else
      only needs HEAD. Depth 0 checks the start URL alone.
    - append an edge ``(page_url, link)`` for EVERY link found (even already-seen ones); only unseen links join the
      next level (cycles and shared links are checked once)
    - only parse a page when ``result.body`` is not None and its final URL is still on the start host
    - store each result in ``report.results[url]`` via ``on_result`` so a cancelled run keeps partial results
    - use ``async with client_factory(config) as client`` so the client is closed even on cancellation
    - on ``asyncio.CancelledError``: set ``report.interrupted = True`` and RE-RAISE
    """
    raise NotImplementedError
