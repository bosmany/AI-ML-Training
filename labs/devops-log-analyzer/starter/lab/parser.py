"""Parse nginx ``combined`` access-log lines (plus a trailing ``request_time`` number).

Line format::

    203.0.113.9 - - [10/Mar/2024:13:55:36 +0000] "GET /a?x=1 HTTP/1.1" 200 512 "-" "curl/8" 0.123
                                                                                 ^ request_time (seconds, optional)
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from datetime import datetime

from .models import LogEntry, ParseStats

# TODO (optional): write the regex yourself. Named groups make it readable.
LINE_RE = re.compile(r"")
TS_FORMAT = "%d/%b/%Y:%H:%M:%S %z"  # for datetime.strptime


def parse_line(line: str) -> LogEntry | None:
    """Return a ``LogEntry`` or ``None`` when the line is not valid combined format.

    TODO:
    - method/path come from the quoted request "GET /a?x=1 HTTP/1.1"; strip the query string from the path.
    - nginx writes "-" as the request for broken clients (400): still a valid line (method "-").
    - "-" for the byte count means 0; request_time is optional (None if absent).
    - a timestamp strptime rejects (e.g. day 32) makes the whole line malformed -> None.
    - never raise for bad input.
    """
    raise NotImplementedError


def iter_entries(lines: Iterable[str], stats: ParseStats | None = None) -> Iterator[LogEntry]:
    """Lazily yield entries from ``lines``.

    TODO: make this a GENERATOR. Pull one line at a time (never build a list of the input), ignore
    blank lines (not counted), count malformed lines in ``stats.skipped`` and good ones in ``stats.parsed``.
    """
    raise NotImplementedError
