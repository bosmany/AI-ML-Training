"""Fixtures: real SQLite files in tmp_path, a controllable clock and deterministic run ids."""

from __future__ import annotations

import itertools
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

TARGET = os.environ.get("LAB_TARGET", "starter")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / TARGET))
sys.dont_write_bytecode = True

import pytest  # noqa: E402

from lab import Registry, Tracker  # noqa: E402


class FakeClock:
    """Returns the same instant until you call ``advance`` - no sleeping, no flakiness."""

    def __init__(self) -> None:
        self.now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float = 1) -> None:
        self.now += timedelta(seconds=seconds)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "tracker.db"


@pytest.fixture
def tracker(db_path, clock):
    counter = itertools.count(1)
    instance = Tracker(db_path, clock=clock, id_factory=lambda: f"run-{next(counter):03d}")
    yield instance
    instance.close()


@pytest.fixture
def registry(db_path, clock):
    instance = Registry(db_path, clock=clock)
    yield instance
    instance.close()


@pytest.fixture
def make_run(tracker, clock):
    """Create a run, log params/metrics, and (by default) finish it. Each run starts 1s after the previous."""

    def _make(
        experiment: str = "exp",
        metrics: dict[str, float] | None = None,
        *,
        params: dict[str, object] | None = None,
        dataset_hash: str | None = "sha256:dataset-v1",
        code_version: str | None = "git:abc1234",
        finish: bool = True,
    ) -> str:
        clock.advance(1)
        run_id = tracker.start_run(experiment, dataset_hash=dataset_hash, code_version=code_version)
        for key, value in (params or {}).items():
            tracker.log_param(run_id, key, value)
        for key, value in (metrics or {}).items():
            tracker.log_metric(run_id, key, value)
        if finish:
            tracker.end_run(run_id)
        return run_id

    return _make
