"""Hysteresis state machine and the rolling window."""

from __future__ import annotations

import pytest

from lab.alerts import HysteresisAlert
from lab.windows import RollingWindow


def test_alert_fires_only_after_n_consecutive_breaches():
    alert = HysteresisAlert(fire_after=3, clear_after=2)
    assert [alert.update(True) for _ in range(3)] == [False, False, True]
    assert alert.firing is True


def test_a_healthy_observation_resets_the_breach_streak():
    alert = HysteresisAlert(fire_after=3, clear_after=2)
    observations = [True, True, False, True, True, False, True, True]  # never 3 in a row
    assert not any(alert.update(b) for b in observations), "flapping input must not fire the alert"
    assert [alert.update(True)] == [True], "but a third consecutive breach does"


def test_alert_clears_only_after_m_consecutive_healthy_observations():
    alert = HysteresisAlert(fire_after=1, clear_after=3)
    assert alert.update(True) is True
    assert [alert.update(False), alert.update(False)] == [True, True], "still firing after 2 healthy checks"
    assert alert.update(True) is True and alert.update(False) is True, "a breach resets the healthy streak"
    assert [alert.update(False), alert.update(False)] == [True, False]
    assert alert.firing is False


def test_alert_rejects_nonsensical_thresholds_and_instances_are_independent():
    for kwargs in ({"fire_after": 0}, {"clear_after": 0}, {"fire_after": -1}):
        with pytest.raises(ValueError):
            HysteresisAlert(**kwargs)
    first, second = HysteresisAlert(1, 1), HysteresisAlert(1, 1)
    first.update(True)
    assert first.firing and not second.firing


def test_rolling_window_keeps_only_the_most_recent_rows_in_order():
    window = RollingWindow(max_rows=4)
    window.add([{"x": 1}, {"x": 2}, {"x": 3}])
    window.add([{"x": 4}, {"x": 5}])
    assert len(window) == 4
    assert window.values("x") == [2, 3, 4, 5], "the oldest row was evicted"
    window.add([{"x": v} for v in range(10, 20)])  # one batch bigger than the whole window
    assert window.values("x") == [16, 17, 18, 19]
    with pytest.raises(ValueError):
        RollingWindow(0)
