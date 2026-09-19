from datetime import datetime, timedelta, timezone

import pytest
from helpers import BASE, at, make_line

from lab import analyze, top_n
from collections import Counter


def test_top_ips_and_paths_sorted_by_count_then_name():
    lines = (
        [make_line(ip="1.1.1.1", path="/a")] * 3
        + [make_line(ip="2.2.2.2", path="/b")] * 3
        + [make_line(ip="0.0.0.9", path="/c")]
    )
    r = analyze(lines, top=2)
    assert r.top_ips == [("1.1.1.1", 3), ("2.2.2.2", 3)], "ties break alphabetically; only `top` rows returned"
    assert r.top_paths == [("/a", 3), ("/b", 3)]
    assert top_n(Counter({"b": 2, "a": 2, "c": 1}), 3) == [("a", 2), ("b", 2), ("c", 1)]


def test_error_rate_counts_only_5xx():
    lines = [make_line(status=s) for s in (200, 404, 500, 502, 503, 301, 401, 599, 600, 499)]
    r = analyze(lines)
    # 500,502,503,599 are 5xx; 600 and 499 are not
    assert r.error_rate == pytest.approx(4 / 10)
    assert r.parsed == 10


def test_hourly_error_rate_buckets_at_hour_boundary():
    lines = [
        make_line(when=datetime(2024, 3, 10, 13, 59, 59, tzinfo=timezone.utc), status=500),
        make_line(when=datetime(2024, 3, 10, 14, 0, 0, tzinfo=timezone.utc), status=200),
        make_line(when=datetime(2024, 3, 10, 14, 0, 1, tzinfo=timezone.utc), status=502),
    ]
    r = analyze(lines)
    got = [(h.hour, h.total, h.errors) for h in r.hourly]
    assert got == [("2024-03-10T13", 1, 1), ("2024-03-10T14", 2, 1)]
    assert r.hourly[1].error_rate == pytest.approx(0.5)


def test_hourly_buckets_use_utc_and_are_sorted_across_midnight():
    tz = timezone(timedelta(hours=2))
    lines = [
        make_line(when=datetime(2024, 3, 11, 0, 5, tzinfo=timezone.utc)),
        make_line(when=datetime(2024, 3, 10, 15, 30, 0, tzinfo=tz), status=500),  # 13:30 UTC
        make_line(when=datetime(2024, 3, 10, 23, 5, tzinfo=timezone.utc)),
    ]
    assert [h.hour for h in analyze(lines).hourly] == ["2024-03-10T13", "2024-03-10T23", "2024-03-11T00"]


def test_latency_percentiles_from_request_time_field():
    lines = [make_line(rt=i / 100, when=at(i)) for i in range(1, 101)]  # 0.01 .. 1.00
    r = analyze(lines)
    assert r.latency["p50"] == pytest.approx(0.50)
    assert r.latency["p95"] == pytest.approx(0.95)
    assert r.latency["p99"] == pytest.approx(0.99)
    only_some = analyze([make_line(rt=None), make_line(rt=2.0), make_line(rt=None)])
    assert only_some.latency == {"p50": 2.0, "p95": 2.0, "p99": 2.0}, "lines without request_time are ignored"


def test_suspicious_ip_only_counts_401_and_403():
    lines = [make_line(ip="6.6.6.6", status=s, when=at(i)) for i, s in enumerate([401, 403, 401, 403, 401])]
    lines += [make_line(ip="5.5.5.5", status=404, when=at(i)) for i in range(10)]
    r = analyze(lines, bf_threshold=5, bf_window=timedelta(seconds=60))
    assert [s.ip for s in r.suspicious] == ["6.6.6.6"], "404s are not auth failures"


def test_analyze_accepts_one_shot_iterator_and_does_not_iterate_twice():
    class OneShot:
        def __init__(self, lines):
            self._it = iter(lines)
            self.iterations = 0

        def __iter__(self):
            self.iterations += 1
            if self.iterations > 1:
                raise AssertionError("input iterated twice - the analyzer must be single-pass")
            return self._it

    src = OneShot([make_line(ip=f"10.0.0.{i}") for i in range(20)])
    r = analyze(src)
    assert r.parsed == 20 and src.iterations == 1


def test_empty_input_gives_zeroed_report_without_dividing_by_zero():
    r = analyze([])
    assert (r.parsed, r.skipped, r.error_rate) == (0, 0, 0.0)
    assert r.top_ips == [] and r.hourly == [] and r.suspicious == []
    assert r.latency["p50"] is None


def test_all_malformed_input_is_counted_as_skipped():
    r = analyze(["junk"] * 4)
    assert (r.parsed, r.skipped) == (0, 4)
    assert r.error_rate == 0.0
