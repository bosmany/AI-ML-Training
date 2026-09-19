"""Statistics helpers: nearest-rank percentiles and a sliding-window brute-force detector."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta

from .models import Suspect


def percentile(values: Sequence[float], p: float) -> float | None:
    """Nearest-rank percentile (``p`` in 0..100). Empty input -> ``None``.

    rank = ceil(p/100 * n), at least 1; result = sorted(values)[rank-1].
    TODO: do not mutate ``values``.
    """
    raise NotImplementedError


class BruteForceDetector:
    """Flag IPs with >= ``threshold`` auth failures inside a sliding window.

    Rule to implement: events are in the same window when (last - first) < ``window`` STRICTLY
    (half-open). Events arrive in chronological order. Memory per IP should stay O(threshold):
    a ``collections.deque(maxlen=threshold)`` of recent timestamps is enough.
    """

    def __init__(self, threshold: int = 5, window: timedelta = timedelta(seconds=60)) -> None:
        # TODO: raise ValueError if threshold < 1; set up per-IP state.
        raise NotImplementedError

    def observe(self, ip: str, ts: datetime) -> bool:
        """Record one failure for ``ip`` at ``ts``; return True if ``ip`` is flagged as of now."""
        raise NotImplementedError

    def suspects(self) -> list[Suspect]:
        """Flagged IPs sorted by IP; ``failures`` = ALL failures seen for that IP (not just in the window),
        ``first_flagged_at`` = timestamp of the event that first tripped the detector."""
        raise NotImplementedError
