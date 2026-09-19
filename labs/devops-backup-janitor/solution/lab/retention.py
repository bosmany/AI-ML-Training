"""Pure retention logic: which backups to keep? No filesystem access here, so it is trivially testable."""
from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass
from datetime import datetime

from .policy import Backup, Policy


@dataclass(frozen=True)
class Decision:
    backup: Backup
    keep: bool
    reasons: tuple[str, ...]


def _day(t: datetime) -> Hashable:
    return (t.year, t.month, t.day)


def _week(t: datetime) -> Hashable:
    iso = t.isocalendar()
    return (iso.year, iso.week)  # ISO year: 2024-12-30 belongs to week 1 of 2025


def _month(t: datetime) -> Hashable:
    return (t.year, t.month)


def _newest_per_bucket(newest_first: list[Backup], n: int, bucket: Callable[[datetime], Hashable]) -> set[Backup]:
    chosen: set[Backup] = set()
    seen: set[Hashable] = set()
    for b in newest_first:
        key = bucket(b.mtime)
        if key in seen:
            continue
        if len(seen) >= n:
            break
        seen.add(key)
        chosen.add(b)
    return chosen


def decide(backups: list[Backup], policy: Policy, now: datetime) -> list[Decision]:
    """One Decision per backup (newest first). Ties in mtime are broken by name, later name = newer."""
    newest_first = sorted(backups, key=lambda b: (b.mtime, b.name), reverse=True)
    reasons: dict[Backup, list[str]] = {b: [] for b in newest_first}
    for b in newest_first[: policy.keep_last]:
        reasons[b].append("last")
    for label, n, bucket in (("daily", policy.keep_daily, _day), ("weekly", policy.keep_weekly, _week),
                             ("monthly", policy.keep_monthly, _month)):
        if n:
            for b in _newest_per_bucket(newest_first, n, bucket):
                reasons[b].append(label)
    for b in newest_first:
        if reasons[b]:
            continue
        if b.mtime > now:  # clock skew or a bogus file: never delete what we cannot date sensibly
            reasons[b].append("future-dated")
        elif now - b.mtime < policy.protect_younger_than:
            reasons[b].append("protected")
    return [Decision(b, bool(reasons[b]), tuple(reasons[b])) for b in newest_first]
