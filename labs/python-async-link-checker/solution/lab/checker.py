"""The async core: one URL, many URLs (gather + semaphore) and a depth-limited crawl."""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Collection
from dataclasses import replace
from urllib.parse import urljoin

import httpx

from .classify import backoff_delay, classify_exception, classify_status
from .models import CheckConfig, LinkResult, Report, Status
from .parsing import extract_links, is_same_host, normalize_url

Sleep = Callable[[float], Awaitable[None]]
ClientFactory = Callable[[CheckConfig], httpx.AsyncClient]

REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})
HEAD_FALLBACK_CODES = frozenset({405, 501})
RETRYABLE = frozenset({Status.TIMEOUT, Status.DNS_ERROR, Status.CONNECTION_ERROR, Status.SERVER_ERROR})


def make_timeout(config: CheckConfig) -> httpx.Timeout:
    """``httpx.Timeout`` with ``config.timeout`` for read/write/pool and ``config.connect_timeout`` for connect."""
    return httpx.Timeout(config.timeout, connect=config.connect_timeout)


def make_client(config: CheckConfig) -> httpx.AsyncClient:
    """A client that does NOT follow redirects itself (we count hops) and uses ``make_timeout``."""
    return httpx.AsyncClient(timeout=make_timeout(config), follow_redirects=False,
                             headers={"User-Agent": "linkcheck-lab/1.0"})


async def _attempt(client: httpx.AsyncClient, url: str, config: CheckConfig, get_body: bool) -> LinkResult:
    started = time.monotonic()
    method = "GET" if get_body else "HEAD"
    current, hops = url, 0
    async with asyncio.timeout(config.timeout):  # total budget for the whole redirect chain
        while True:
            response = await client.request(method, current)
            code = response.status_code
            if method == "HEAD" and code in HEAD_FALLBACK_CODES:
                method = "GET"  # some servers do not implement HEAD: retry the same URL with GET
                continue
            location = response.headers.get("location")
            if code in REDIRECT_CODES and location:
                if hops >= config.max_redirects:
                    return LinkResult(url, Status.TOO_MANY_REDIRECTS, code, current, time.monotonic() - started,
                                      error=f"more than {config.max_redirects} redirects")
                hops += 1
                current = urljoin(current, location)
                continue
            break
    status = classify_status(code)
    if hops and status is Status.OK:
        status = Status.REDIRECT
    content_type = response.headers.get("content-type")
    body = response.text if get_body and not status.is_broken and "html" in (content_type or "").lower() else None
    return LinkResult(url, status, code, current if hops else None, time.monotonic() - started,
                      content_type=content_type, body=body)


async def check_url(client: httpx.AsyncClient, url: str, config: CheckConfig, *, get_body: bool = False,
                    sleep: Sleep = asyncio.sleep) -> LinkResult:
    """Check ONE url with retries. Never raises for network problems (they become results)."""
    attempts = 0
    while True:
        attempts += 1
        started = time.monotonic()
        try:
            result = await _attempt(client, url, config, get_body)
        except Exception as exc:  # CancelledError is a BaseException: it propagates
            status, message = classify_exception(exc)  # re-raises anything that is not a network failure
            result = LinkResult(url, status, latency=time.monotonic() - started, error=message)
        if result.status not in RETRYABLE or attempts > config.retries:
            return replace(result, attempts=attempts)
        await sleep(backoff_delay(attempts - 1, config.backoff_base))


async def check_urls(urls: Collection[str], config: CheckConfig, *, client: httpx.AsyncClient | None = None,
                     body_urls: Collection[str] = (), sleep: Sleep = asyncio.sleep,
                     on_result: Callable[[LinkResult], None] | None = None) -> list[LinkResult]:
    """Check every distinct URL concurrently, at most ``config.concurrency`` in flight.

    Results come back in the order of first appearance in ``urls`` (duplicates are checked once).
    ``body_urls`` are fetched with GET so their HTML is available; the rest use HEAD first.
    ``on_result`` is called as each URL finishes (used for partial reports).
    """
    config.validate()
    unique = list(dict.fromkeys(urls))
    if client is None:
        async with make_client(config) as own_client:
            return await check_urls(unique, config, client=own_client, body_urls=body_urls, sleep=sleep,
                                    on_result=on_result)
    semaphore = asyncio.Semaphore(config.concurrency)
    wants_body = set(body_urls)

    async def worker(url: str) -> LinkResult:
        async with semaphore:
            result = await check_url(client, url, config, get_body=url in wants_body, sleep=sleep)
        if on_result is not None:
            on_result(result)
        return result

    tasks = [asyncio.ensure_future(worker(u)) for u in unique]
    try:
        return list(await asyncio.gather(*tasks))
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)  # leave no pending tasks behind
        raise


async def crawl(start_url: str, config: CheckConfig, *, depth: int = 1, client_factory: ClientFactory = make_client,
                report: Report | None = None, sleep: Sleep = asyncio.sleep) -> Report:
    """Check ``start_url`` and the links found on same-host pages up to ``depth`` hops away.

    Depth 0 checks only the start URL. Pages closer than ``depth`` are fetched with GET and parsed (only same-host,
    HTML pages); everything else is checked with HEAD. Each URL is checked once. If the task is cancelled the client
    is closed, ``report.interrupted`` is set and ``CancelledError`` propagates; results gathered so far stay in ``report``.
    """
    config.validate()
    if depth < 0:
        raise ValueError("depth must be >= 0")
    start = normalize_url(start_url)
    if report is None:
        report = Report(start_url=start)
    report.edges.append((None, start))
    seen = {start}
    frontier: list[str] = [start]

    def record(result: LinkResult) -> None:
        report.results[result.url] = result

    try:
        async with client_factory(config) as client:
            for level in range(depth + 1):
                if not frontier:
                    break
                parse_pages = level < depth
                body_urls = {u for u in frontier if parse_pages and is_same_host(u, start)}
                results = await check_urls(frontier, config, client=client, body_urls=body_urls, sleep=sleep,
                                           on_result=record)
                frontier = []
                for result in results:
                    page = result.final_url or result.url
                    if result.body is None or not is_same_host(page, start):
                        continue
                    for link in extract_links(result.body, page):
                        report.edges.append((result.url, link))
                        if link not in seen:
                            seen.add(link)
                            frontier.append(link)
    except asyncio.CancelledError:
        report.interrupted = True
        raise
    return report
