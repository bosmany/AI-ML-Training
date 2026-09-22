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
        """Raise ``ValueError`` (naming the field) for a nonsensical configuration.

        TODO: concurrency >= 1; timeout and connect_timeout > 0; retries >= 0; backoff_base >= 0; max_redirects >= 0.
        """
        raise NotImplementedError


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
        """Results whose status ``is_broken``, sorted by URL.

        TODO: implement.
        """
        raise NotImplementedError

    def to_json_dict(self) -> dict[str, Any]:
        """A plain-JSON view of the report.

        TODO: return ``{"start_url", "interrupted", "checked": len(results), "broken": len(broken), "links": [...]}``
        where ``links`` has one row per entry of ``edges`` whose target already has a result (an interrupted run has
        edges without results - skip those). Row keys: ``source`` (None for the start URL), ``url``, ``status``
        (the enum VALUE, e.g. "client_error"), ``http_status``, ``final_url``, ``latency_ms`` (seconds * 1000, rounded
        to 1 decimal), ``attempts``, ``error``.
        """
        raise NotImplementedError
