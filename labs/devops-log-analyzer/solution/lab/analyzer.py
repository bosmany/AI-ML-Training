"""Single-pass aggregation over a stream of ``LogEntry`` objects."""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import timedelta, timezone

from .models import HourStat, LogEntry, ParseStats, Report
from .parser import iter_entries
from .stats import BruteForceDetector, percentile

AUTH_FAILURE_STATUSES = frozenset({401, 403})


def top_n(counter: Counter[str], n: int) -> list[tuple[str, int]]:
    """Highest counts first; ties broken alphabetically so output is deterministic."""
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


class Analyzer:
    def __init__(self, top: int = 5, bf_threshold: int = 5, bf_window: timedelta = timedelta(seconds=60)) -> None:
        self.top = top
        self._ips: Counter[str] = Counter()
        self._paths: Counter[str] = Counter()
        self._hour_total: Counter[str] = Counter()
        self._hour_errors: Counter[str] = Counter()
        self._times: list[float] = []
        self._detector = BruteForceDetector(bf_threshold, bf_window)
        self._total = 0
        self._errors = 0

    def feed(self, entry: LogEntry) -> None:
        self._total += 1
        self._ips[entry.ip] += 1
        self._paths[entry.path] += 1
        hour = entry.timestamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H")
        self._hour_total[hour] += 1
        if 500 <= entry.status <= 599:
            self._errors += 1
            self._hour_errors[hour] += 1
        if entry.request_time is not None:
            self._times.append(entry.request_time)
        if entry.status in AUTH_FAILURE_STATUSES:
            self._detector.observe(entry.ip, entry.timestamp)

    def report(self, stats: ParseStats | None = None) -> Report:
        stats = stats or ParseStats(parsed=self._total)
        return Report(
            parsed=stats.parsed,
            skipped=stats.skipped,
            error_rate=self._errors / self._total if self._total else 0.0,
            top_ips=top_n(self._ips, self.top),
            top_paths=top_n(self._paths, self.top),
            hourly=[HourStat(h, self._hour_total[h], self._hour_errors[h]) for h in sorted(self._hour_total)],
            latency={f"p{p}": percentile(self._times, p) for p in (50, 95, 99)},
            suspicious=self._detector.suspects(),
        )


def analyze(
    lines: Iterable[str],
    top: int = 5,
    bf_threshold: int = 5,
    bf_window: timedelta = timedelta(seconds=60),
) -> Report:
    """Stream ``lines`` once and return a ``Report``. ``lines`` may be a one-shot iterator."""
    stats = ParseStats()
    analyzer = Analyzer(top, bf_threshold, bf_window)
    for entry in iter_entries(lines, stats):
        analyzer.feed(entry)
    return analyzer.report(stats)
