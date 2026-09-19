from datetime import datetime, timedelta, timezone

import pytest
from helpers import at, make_line

from lab import ParseStats, iter_entries, parse_line


def test_parse_line_extracts_all_fields():
    e = parse_line('203.0.113.9 - bob [10/Mar/2024:13:55:36 +0200] "POST /api/v1/login?next=/home HTTP/1.1" '
                   '401 1234 "https://example.com/" "Mozilla/5.0 (X11; Linux)" 0.482')
    assert e is not None, "a valid combined-format line must parse"
    assert e.ip == "203.0.113.9"
    assert e.method == "POST"
    assert e.path == "/api/v1/login", "query string must be stripped so /a?x=1 and /a?x=2 count as one path"
    assert e.status == 401
    assert e.bytes_sent == 1234
    assert e.request_time == pytest.approx(0.482)
    assert e.timestamp.utcoffset() == timedelta(hours=2), "keep the timezone from the log"
    assert e.timestamp == datetime(2024, 3, 10, 11, 55, 36, tzinfo=timezone.utc)


def test_parse_line_tolerates_nginx_quirks():
    no_rt = parse_line(make_line(rt=None))
    assert no_rt is not None and no_rt.request_time is None, "request_time is optional"
    dash = parse_line('1.2.3.4 - - [10/Mar/2024:13:00:00 +0000] "GET / HTTP/1.1" 304 - "-" "ua" 0.001')
    assert dash is not None and dash.bytes_sent == 0, "'-' bytes means 0"
    broken = parse_line('1.2.3.4 - - [10/Mar/2024:13:00:00 +0000] "-" 400 0 "-" "-" 0.000')
    assert broken is not None and broken.status == 400, 'nginx logs "-" for broken requests; still a valid line'
    ua = parse_line(make_line(ua="Mozilla/5.0 [weird] (KHTML, like Gecko)", path="/x"))
    assert ua is not None and ua.path == "/x", "spaces/brackets in the user agent must not confuse the parser"


BAD_LINES = [
        "",  # empty is handled by iter_entries, but parse_line must not crash
        "garbage",
        '1.2.3.4 - - [not a date] "GET / HTTP/1.1" 200 5 "-" "ua"',
        '1.2.3.4 - - [10/Mar/2024:13:00:00 +0000] "GET / HTTP/1.1" 20 5 "-" "ua"',  # 2-digit status
        '1.2.3.4 - - [10/Mar/2024:13:00:00 +0000] "GET / HTTP/1.1" 200 5 "-"',  # missing UA
        '1.2.3.4 - - [32/Mar/2024:13:00:00 +0000] "GET / HTTP/1.1" 200 5 "-" "ua"',  # day 32
    ]


def test_parse_line_returns_none_for_malformed():
    for bad in BAD_LINES:
        assert parse_line(bad) is None, f"should be rejected: {bad!r}"


def test_iter_entries_counts_skipped_and_ignores_blank_lines():
    lines = [make_line(), "", "   \n", "not a log line", make_line(status=500), "\x00\x01binary"]
    stats = ParseStats()
    entries = list(iter_entries(lines, stats))
    assert [e.status for e in entries] == [200, 500]
    assert (stats.parsed, stats.skipped) == (2, 2), "blank lines are ignored, only garbage counts as skipped"


def test_iter_entries_is_lazy_and_pulls_one_line_per_entry():
    pulled = []

    def source():
        for i in range(1000):
            pulled.append(i)
            yield make_line(when=at(i))

    gen = iter_entries(source())
    assert pulled == [], "creating the generator must not read anything"
    next(gen)
    assert pulled == [0], "one entry requested -> exactly one line read; do not read ahead or build a list"
    next(gen)
    assert pulled == [0, 1]


def test_iter_entries_yields_before_a_later_line_would_blow_up():
    def source():
        yield make_line()
        yield make_line()
        raise RuntimeError("input consumed further than needed")

    gen = iter_entries(source())
    assert next(gen).status == 200
    assert next(gen).status == 200  # would raise if the implementation slurped the input first
