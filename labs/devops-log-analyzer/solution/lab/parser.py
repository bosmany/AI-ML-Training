"""Parse nginx ``combined`` access-log lines (plus a trailing ``request_time`` number).

Line format::

    203.0.113.9 - - [10/Mar/2024:13:55:36 +0000] "GET /a?x=1 HTTP/1.1" 200 512 "-" "curl/8" 0.123
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from datetime import datetime

from .models import LogEntry, ParseStats

LINE_RE = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[(?P<ts>[^\]]+)\] "(?P<req>[^"]*)" (?P<status>\d{3}) '
    r'(?P<bytes>\d+|-) "(?P<ref>[^"]*)" "(?P<ua>[^"]*)"(?: (?P<rt>\d+(?:\.\d+)?))?\s*$'
)
TS_FORMAT = "%d/%b/%Y:%H:%M:%S %z"


def parse_line(line: str) -> LogEntry | None:
    """Return a ``LogEntry`` or ``None`` when the line is not valid combined format."""
    m = LINE_RE.match(line.rstrip("\r\n"))
    if m is None:
        return None
    try:
        ts = datetime.strptime(m["ts"], TS_FORMAT)
    except ValueError:
        return None
    parts = m["req"].split(" ")
    if len(parts) == 3:
        method, target = parts[0], parts[1]
    else:  # nginx logs "-" for requests it could not parse (e.g. 400 Bad Request)
        method, target = "-", m["req"] or "-"
    path = target.split("?", 1)[0] or "/"
    return LogEntry(
        ip=m["ip"],
        timestamp=ts,
        method=method,
        path=path,
        status=int(m["status"]),
        bytes_sent=0 if m["bytes"] == "-" else int(m["bytes"]),
        request_time=float(m["rt"]) if m["rt"] is not None else None,
    )


def iter_entries(lines: Iterable[str], stats: ParseStats | None = None) -> Iterator[LogEntry]:
    """Lazily yield entries; blank lines are ignored, bad lines increment ``stats.skipped``.

    This is a generator: it pulls ONE line from ``lines`` per step and never materialises
    the whole input.
    """
    stats = stats if stats is not None else ParseStats()
    for line in lines:
        if not line.strip():
            continue
        entry = parse_line(line)
        if entry is None:
            stats.skipped += 1
            continue
        stats.parsed += 1
        yield entry
