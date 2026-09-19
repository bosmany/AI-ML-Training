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


# Bucket keys (given). All times are UTC. ISO weeks: Monday-Sunday, and the ISO *year* can differ from the
# calendar year around New Year (2024-12-30 is week 1 of 2025).
def _day(t: datetime) -> Hashable:
    return (t.year, t.month, t.day)


def _week(t: datetime) -> Hashable:
    iso = t.isocalendar()
    return (iso.year, iso.week)


def _month(t: datetime) -> Hashable:
    return (t.year, t.month)


def _newest_per_bucket(newest_first: list[Backup], n: int, bucket: Callable[[datetime], Hashable]) -> set[Backup]:
    """TODO: walk newest -> oldest; the first backup seen in each NEW bucket is chosen; stop after ``n`` buckets.
    Buckets are the ones that HAVE backups: a gap of empty days must not use up the budget."""
    raise NotImplementedError


def decide(backups: list[Backup], policy: Policy, now: datetime) -> list[Decision]:
    """One Decision per backup, newest first (ties in mtime: later NAME counts as newer, for determinism).

    Rules are OR-ed; ``reasons`` lists why a backup is kept: "last", "daily", "weekly", "monthly".
    A backup no rule keeps is still kept when
      - its mtime is in the future (> now): reason "future-dated" (clock skew; never delete what you cannot date)
      - its age is STRICTLY less than ``policy.protect_younger_than``: reason "protected"
    """
    raise NotImplementedError
