"""Statistics helpers: nearest-rank percentiles and a sliding-window brute-force detector."""
from __future__ import annotations

import math
from collections import Counter, deque
from collections.abc import Sequence
from datetime import datetime, timedelta

from .models import Suspect


def percentile(values: Sequence[float], p: float) -> float | None:
    """Nearest-rank percentile (``p`` in 0..100). Empty input -> ``None``.

    rank = ceil(p/100 * n) (at least 1); result = sorted(values)[rank-1].
    """
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


class BruteForceDetector:
    """Flag IPs with >= ``threshold`` auth failures inside a sliding window.

    Window rule: events are "in the same window" when the span between the first and the last
    is STRICTLY LESS than ``window`` (half-open). 5 failures at t=0..59s with window 60s are
    flagged; the same 5 failures at t=0..60s are not.
    Events must be fed in chronological order. Memory per IP is O(threshold).
    """

    def __init__(self, threshold: int = 5, window: timedelta = timedelta(seconds=60)) -> None:
        if threshold < 1:
            raise ValueError("threshold must be >= 1")
        self.threshold = threshold
        self.window = window
        self._recent: dict[str, deque[datetime]] = {}
        self._failures: Counter[str] = Counter()
        self._flagged_at: dict[str, datetime] = {}

    def observe(self, ip: str, ts: datetime) -> bool:
        """Record one failure; return True if ``ip`` is flagged as of this event."""
        self._failures[ip] += 1
        recent = self._recent.setdefault(ip, deque(maxlen=self.threshold))
        recent.append(ts)
        if len(recent) == self.threshold and ts - recent[0] < self.window:
            self._flagged_at.setdefault(ip, ts)
        return ip in self._flagged_at

    def suspects(self) -> list[Suspect]:
        return [Suspect(ip, self._failures[ip], self._flagged_at[ip]) for ip in sorted(self._flagged_at)]
