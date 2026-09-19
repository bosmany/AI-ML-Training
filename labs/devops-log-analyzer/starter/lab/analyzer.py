"""Single-pass aggregation over a stream of ``LogEntry`` objects."""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import timedelta

from .models import LogEntry, ParseStats, Report

AUTH_FAILURE_STATUSES = frozenset({401, 403})


def top_n(counter: Counter[str], n: int) -> list[tuple[str, int]]:
    """Highest counts first; ties broken alphabetically by key so output is deterministic."""
    raise NotImplementedError


class Analyzer:
    """Accumulate statistics one entry at a time (constant memory except the list of request times)."""

    def __init__(self, top: int = 5, bf_threshold: int = 5, bf_window: timedelta = timedelta(seconds=60)) -> None:
        # TODO: Counters for IPs, paths, per-hour totals/5xx; list of request times; a BruteForceDetector.
        raise NotImplementedError

    def feed(self, entry: LogEntry) -> None:
        """TODO: update every aggregate.

        - 5xx means 500..599 inclusive (499 and 600 are NOT errors).
        - hour bucket key: entry.timestamp converted to UTC, formatted "%Y-%m-%dT%H".
        - only 401 and 403 feed the brute-force detector.
        """
        raise NotImplementedError

    def report(self, stats: ParseStats | None = None) -> Report:
        """TODO: build the Report. hourly sorted chronologically; latency keys "p50","p95","p99"
        (None when no request_time was seen); error_rate = 5xx / parsed (0.0 when nothing parsed)."""
        raise NotImplementedError


def analyze(
    lines: Iterable[str],
    top: int = 5,
    bf_threshold: int = 5,
    bf_window: timedelta = timedelta(seconds=60),
) -> Report:
    """Stream ``lines`` ONCE (they may be a one-shot iterator) and return a ``Report``.

    Hint: ParseStats + iter_entries + Analyzer.
    """
    raise NotImplementedError
