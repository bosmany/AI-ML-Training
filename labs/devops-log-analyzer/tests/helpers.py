"""Fixture-building helpers (kept out of conftest so the tests can import them plainly)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

BASE = datetime(2024, 3, 10, 13, 0, 0, tzinfo=timezone.utc)


def stamp(dt: datetime) -> str:
    return dt.strftime("%d/%b/%Y:%H:%M:%S %z")


def make_line(ip="10.0.0.1", when=BASE, status=200, path="/", method="GET", rt: float | None = 0.05,
              size=512, ua="curl/8.0") -> str:
    tail = "" if rt is None else f" {rt}"
    return f'{ip} - - [{stamp(when)}] "{method} {path} HTTP/1.1" {status} {size} "-" "{ua}"{tail}'


def at(seconds: float) -> datetime:
    return BASE + timedelta(seconds=seconds)
