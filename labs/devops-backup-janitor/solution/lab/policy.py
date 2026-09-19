"""Retention policy, backup records and policy-string parsing."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class Policy:
    """How many backups to keep. Rules are OR-ed together (a backup kept by any rule is kept).

    keep_last     the N most recent backups
    keep_daily    the newest backup of each of the N most recent DAYS that have a backup (UTC)
    keep_weekly   ... of each of the N most recent ISO WEEKS that have a backup
    keep_monthly  ... of each of the N most recent MONTHS that have a backup
    protect_younger_than  never delete anything younger than this (protects a backup still being written)
    """

    keep_last: int = 0
    keep_daily: int = 0
    keep_weekly: int = 0
    keep_monthly: int = 0
    protect_younger_than: timedelta = timedelta(0)

    def __post_init__(self) -> None:
        counts = (self.keep_last, self.keep_daily, self.keep_weekly, self.keep_monthly)
        if any(c < 0 for c in counts):
            raise ValueError("keep-* values must not be negative")
        if not any(counts):
            raise ValueError("a policy with every keep-* rule at 0 would delete ALL backups; refusing")
        if self.protect_younger_than < timedelta(0):
            raise ValueError("protect_younger_than must not be negative")


@dataclass(frozen=True)
class Backup:
    path: Path
    name: str
    series: str
    mtime: datetime  # timezone-aware UTC


_SERIES_RE = re.compile(r"^(?P<series>.+?)-\d{4}")


def series_of(name: str) -> str | None:
    """"db-prod-2024-03-01.tar.gz" -> "db-prod"; "logs-20240301.tgz" -> "logs"; no match -> None."""
    m = _SERIES_RE.match(name)
    return m["series"] if m else None


_KEYS = {"last": "keep_last", "daily": "keep_daily", "weekly": "keep_weekly", "monthly": "keep_monthly"}


def parse_policy(spec: str, protect_younger_than: timedelta = timedelta(0)) -> Policy:
    """"last:3,daily:7,monthly:6" -> Policy(keep_last=3, keep_daily=7, keep_monthly=6)."""
    values: dict[str, int] = {}
    for part in spec.split(","):
        key, sep, raw = part.strip().partition(":")
        if not sep or key not in _KEYS or key in values:
            raise ValueError(f"bad policy item {part!r}; use last|daily|weekly|monthly:N, e.g. last:3,daily:7")
        try:
            n = int(raw)
        except ValueError:
            raise ValueError(f"bad number in policy item {part!r}") from None
        values[key] = n
    return Policy(**{_KEYS[k]: n for k, n in values.items()}, protect_younger_than=protect_younger_than)
