"""A tiny local HTTP site for hermetic link-checker tests. Binds 127.0.0.1 on a free port; no real network.

It records what the checker does so tests can assert with COUNTERS instead of sleeping:
  * ``requests``       every (method, path) received, in order
  * ``max_in_flight``  highest number of requests being handled at the same moment
Each route can add latency, hang, fail its first N requests, answer HEAD differently, or wait until a peak
concurrency has been observed (which makes "the limit is really reached" deterministic).
"""
from __future__ import annotations

import socket
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


@dataclass
class Route:
    status: int = 200
    body: str = ""
    content_type: str = "text/html; charset=utf-8"
    headers: dict[str, str] = field(default_factory=dict)
    delay: float = 0.0             # server-side latency in seconds
    hang: bool = False             # never answer (until the site stops)
    fail_first: int = 0            # answer 503 to the first N requests for this path, then behave normally
    head_status: int | None = None  # different status for HEAD requests (e.g. 405)
    hold_until_peak: int = 0       # hold each request until `n` requests were in flight at once (max 1 s)


def closed_port() -> int:
    """A loopback port nothing listens on (connection refused, no DNS, no internet)."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FixtureSite:
    def __init__(self) -> None:
        self.routes: dict[str, Route] = {}
        self.requests: list[tuple[str, str]] = []
        self.in_flight = 0
        self.max_in_flight = 0
        self._hits: dict[str, int] = {}
        self._cond = threading.Condition()
        self._stop = threading.Event()
        site = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:  # noqa: N802
                site._handle(self, "GET")

            def do_HEAD(self) -> None:  # noqa: N802
                site._handle(self, "HEAD")

            def log_message(self, *args: object) -> None:
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)

    # ---- configuration -------------------------------------------------------------------------------------
    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def url(self, path: str = "/") -> str:
        return self.base + path

    def add(self, path: str, **kwargs: object) -> Route:
        route = Route(**kwargs)  # type: ignore[arg-type]
        self.routes[path] = route
        return route

    def page(self, path: str, links: list[str] | None = None, **kwargs: object) -> Route:
        anchors = "".join(f'<a href="{href}">link</a>\n' for href in (links or []))
        return self.add(path, body=f"<html><body>{anchors}</body></html>", **kwargs)

    # ---- observation ---------------------------------------------------------------------------------------
    def count(self, path: str | None = None, method: str | None = None) -> int:
        with self._cond:
            return sum(1 for m, p in self.requests if (path is None or p == path) and (method is None or m == method))

    def wait_for_in_flight(self, n: int, timeout: float = 5.0) -> bool:
        """Block (call it via ``asyncio.to_thread``) until ``n`` requests are being handled at once."""
        with self._cond:
            return self._cond.wait_for(lambda: self.in_flight >= n, timeout)

    # ---- lifecycle -----------------------------------------------------------------------------------------
    def start(self) -> "FixtureSite":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()  # releases hanging handlers
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    # ---- request handling ----------------------------------------------------------------------------------
    def _handle(self, handler: BaseHTTPRequestHandler, method: str) -> None:
        raw_path = handler.path
        path = urlsplit(raw_path).path
        with self._cond:
            self.requests.append((method, path))
            self._hits[path] = self._hits.get(path, 0) + 1
            hit_number = self._hits[path]
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
            self._cond.notify_all()
        route = self.routes.get(path)
        try:
            if route is None:
                status, body, ctype, headers = 404, "not found", "text/plain", {}
            else:
                if route.hold_until_peak:
                    with self._cond:
                        self._cond.wait_for(lambda: self.max_in_flight >= route.hold_until_peak or self._stop.is_set(),
                                            timeout=1.0)
                if route.hang:
                    self._stop.wait(60)
                if route.delay:
                    time.sleep(route.delay)
                status = 503 if hit_number <= route.fail_first else route.status
                if method == "HEAD" and route.head_status is not None:
                    status = route.head_status
                body, ctype, headers = route.body, route.content_type, route.headers
        finally:
            # Count the request as finished BEFORE the response is written, otherwise a client that starts its next
            # request the instant it sees this response could be counted as "concurrent" with this one.
            with self._cond:
                self.in_flight -= 1
                self._cond.notify_all()
        payload = body.encode()
        try:
            handler.send_response(status)
            handler.send_header("Content-Type", ctype)
            handler.send_header("Content-Length", str(len(payload)))
            for name, value in headers.items():
                handler.send_header(name, value)
            handler.end_headers()
            if method != "HEAD":
                handler.wfile.write(payload)
        except OSError:
            pass  # the client gave up (timeout / cancel)
