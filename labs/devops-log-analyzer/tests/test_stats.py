from datetime import timedelta

import pytest
from helpers import at

from lab import BruteForceDetector, percentile


def test_percentile_nearest_rank_on_one_to_hundred():
    data = list(range(1, 101))
    assert percentile(data, 50) == 50
    assert percentile(data, 95) == 95
    assert percentile(data, 99) == 99
    assert percentile(data, 100) == 100


def test_percentile_unsorted_input_is_not_mutated():
    data = [0.9, 0.1, 0.5]
    assert percentile(data, 50) == 0.5
    assert data == [0.9, 0.1, 0.5], "percentile must not sort the caller's list in place"


def test_percentile_small_samples_extremes_and_empty():
    assert percentile([7.0], 99) == 7.0
    assert percentile([1.0, 2.0], 50) == 1.0, "nearest rank: ceil(0.5*2)=1 -> first element"
    assert percentile([1.0, 2.0, 3.0], 0) == 1.0, "p0 is the minimum, not an index error"
    assert percentile([], 95) is None


def test_bruteforce_flags_burst_inside_window():
    d = BruteForceDetector(threshold=5, window=timedelta(seconds=60))
    results = [d.observe("9.9.9.9", at(t)) for t in (0, 10, 20, 30, 59)]
    assert results == [False, False, False, False, True]
    (s,) = d.suspects()
    assert s.ip == "9.9.9.9" and s.failures == 5 and s.first_flagged_at == at(59)


def test_bruteforce_window_edge_is_half_open():
    edge = BruteForceDetector(threshold=5, window=timedelta(seconds=60))
    for t in (0, 15, 30, 45, 60):  # span == window -> NOT the same window
        edge.observe("9.9.9.9", at(t))
    assert edge.suspects() == [], "span of exactly `window` must not count; window is [t, t+window)"
    inside = BruteForceDetector(threshold=5, window=timedelta(seconds=60))
    for t in (0, 15, 30, 45, 59.999):
        inside.observe("9.9.9.9", at(t))
    assert [s.ip for s in inside.suspects()] == ["9.9.9.9"], "a hair inside the edge is flagged"


def test_bruteforce_slow_trickle_is_not_flagged_and_window_slides():
    slow = BruteForceDetector(threshold=3, window=timedelta(seconds=60))
    for t in range(0, 600, 40):  # 15 failures, never 3 inside one minute
        slow.observe("8.8.8.8", at(t))
    assert slow.suspects() == []
    d = BruteForceDetector(threshold=3, window=timedelta(seconds=10))
    # 2 old failures, a long gap, then 2 new ones: never 3 inside 10 s.
    for t in (0, 1, 100, 101):
        d.observe("7.7.7.7", at(t))
    assert d.suspects() == []
    d.observe("7.7.7.7", at(102))  # 100,101,102 -> burst
    assert [s.ip for s in d.suspects()] == ["7.7.7.7"]


def test_bruteforce_tracks_ips_independently():
    d = BruteForceDetector(threshold=3, window=timedelta(seconds=60))
    for i, ip in enumerate(["a", "b", "a", "b", "a", "b"]):
        d.observe(ip, at(i))
    assert [s.ip for s in d.suspects()] == ["a", "b"], "suspects are returned sorted by IP"
    d2 = BruteForceDetector(threshold=3, window=timedelta(seconds=60))
    for i, ip in enumerate(["a", "b", "c", "a", "b", "c"]):
        d2.observe(ip, at(i))
    assert d2.suspects() == [], "2 failures each: failures from different IPs must not be pooled"


def test_bruteforce_threshold_validation():
    with pytest.raises(ValueError):
        BruteForceDetector(threshold=0)
