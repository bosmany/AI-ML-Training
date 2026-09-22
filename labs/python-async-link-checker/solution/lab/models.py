"""Data types shared by every module. Provided in the starter except where a TODO says otherwise."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Status(str, Enum):
    OK = "ok"
    REDIRECT = "redirect"                       # followed >= 1 redirect and the final response was 2xx
    CLIENT_ERROR = "client_error"               # 4xx (and unexpected codes such as a 3xx without Location)
    SERVER_ERROR = "server_error"               # 5xx
    TIMEOUT = "timeout"
    DNS_ERROR = "dns_error"
    CONNECTION_ERROR = "connection_error"       # refused, reset, TLS failure...
    TOO_MANY_REDIRECTS = "too_many_redirects"

    @property
    def is_broken(self) -> bool:
        return self not in (Status.OK, Status.REDIRECT)


@dataclass(frozen=True)
class CheckConfig:
    concurrency: int = 10          # max requests in flight
    timeout: float = 10.0          # TOTAL seconds per attempt (whole redirect chain included)
    connect_timeout: float = 5.0   # seconds to establish the TCP connection
    retries: int = 0               # extra attempts after the first for transient failures
    backoff_base: float = 0.5      # delay before retry n is min(30, base * 2**n)
    max_redirects: int = 5

    def validate(self) -> None:
        """Raise ``ValueError`` (naming the field) for a nonsensical configuration."""
        if self.concurrency < 1:
            raise ValueError("concurrency must be at least 1")
        if self.timeout <= 0 or self.connect_timeout <= 0:
            raise ValueError("timeout and connect_timeout must be positive")
        if self.retries < 0:
            raise ValueError("retries must be >= 0")
        if self.backoff_base < 0:
            raise ValueError("backoff_base must be >= 0")
        if self.max_redirects < 0:
            raise ValueError("max_redirects must be >= 0")


@dataclass(frozen=True)
class LinkResult:
    url: str
    status: Status
    http_status: int | None = None       # status code of the FINAL response, None if there was none
    final_url: str | None = None         # set when redirects were followed
    latency: float = 0.0                 # seconds spent on the last attempt
    attempts: int = 1
    error: str | None = None
    content_type: str | None = None
    body: str | None = field(default=None, repr=False, compare=False)  # only for pages that were fetched with GET


@dataclass
class Report:
    start_url: str
    results: dict[str, LinkResult] = field(default_factory=dict)   # one entry per unique URL checked
    edges: list[tuple[str | None, str]] = field(default_factory=list)  # (source page or None, target URL)
    interrupted: bool = False

    @property
    def broken(self) -> list[LinkResult]:
        """Broken results, sorted by URL."""
        return sorted((r for r in self.results.values() if r.status.is_broken), key=lambda r: r.url)

    def to_json_dict(self) -> dict[str, Any]:
        """``{"start_url", "interrupted", "checked", "broken", "links": [row per edge whose target has a result]}``.

        Row keys: source (None for the start URL), url, status (the enum value), http_status, final_url,
        latency_ms (rounded to 1 decimal), attempts, error.
        """
        links = []
        for source, target in self.edges:
            r = self.results.get(target)
            if r is None:
                continue  # discovered but not checked yet (interrupted run)
            links.append({"source": source, "url": r.url, "status": r.status.value, "http_status": r.http_status,
                          "final_url": r.final_url, "latency_ms": round(r.latency * 1000, 1),
                          "attempts": r.attempts, "error": r.error})
        return {"start_url": self.start_url, "interrupted": self.interrupted, "checked": len(self.results),
                "broken": len(self.broken), "links": links}
