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
        # TODO (safety!): raise ValueError when any keep-* value is negative, when protect_younger_than is
        # negative, and when EVERY keep-* rule is 0 (that policy would delete all backups - refuse, message
        # must contain "delete ALL").
        pass


@dataclass(frozen=True)
class Backup:
    path: Path
    name: str
    series: str
    mtime: datetime  # timezone-aware UTC


_SERIES_RE = re.compile(r"^(?P<series>.+?)-\d{4}")


def series_of(name: str) -> str | None:
    """"db-prod-2024-03-01.tar.gz" -> "db-prod"; "logs-20240301.tgz" -> "logs"; no match -> None.

    The series is everything before the first "-" that is followed by 4 digits (_SERIES_RE is given).
    """
    raise NotImplementedError


_KEYS = {"last": "keep_last", "daily": "keep_daily", "weekly": "keep_weekly", "monthly": "keep_monthly"}


def parse_policy(spec: str, protect_younger_than: timedelta = timedelta(0)) -> Policy:
    """"last:3,daily:7,monthly:6" -> Policy(keep_last=3, keep_daily=7, keep_monthly=6).

    TODO: whitespace around items is fine. Raise ValueError for: empty spec, item without ":", unknown key,
    duplicate key, non-integer or negative number (the Policy validation catches negatives/all-zero).
    """
    raise NotImplementedError
