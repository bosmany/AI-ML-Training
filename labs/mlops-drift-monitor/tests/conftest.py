"""Fixtures: a deterministic config (hand-built arrays, no randomness) and an app per test."""

from __future__ import annotations

import os
import sys
from pathlib import Path

TARGET = os.environ.get("LAB_TARGET", "starter")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / TARGET))
sys.dont_write_bytecode = True

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from prometheus_client.parser import text_string_to_metric_families  # noqa: E402

from lab.app import create_app  # noqa: E402
from lab.config import FeatureSpec, MonitorConfig  # noqa: E402

REFERENCE_AGES = [float(age) for age in range(20, 70)]  # 50 evenly spread values
REFERENCE_PLANS = ["free"] * 30 + ["pro"] * 20  # 60 % / 40 %

# 20 rows spread evenly over the same range: looks like the reference
HEALTHY_AGES = [20.0 + i * 49 / 19 for i in range(20)]
HEALTHY_PLANS = ["free"] * 12 + ["pro"] * 8
# 20 rows all above the reference's 90th percentile: a strong shift
DRIFTED_AGES = [65.0 + i * 0.5 for i in range(20)]
DRIFTED_PLANS = ["pro"] * 20


def make_config(**overrides) -> MonitorConfig:
    values = dict(
        reference={"age": REFERENCE_AGES, "plan": REFERENCE_PLANS},
        features=(FeatureSpec("age", "numeric"), FeatureSpec("plan", "categorical")),
        window_size=20,
        min_window_rows=10,
        n_bins=5,
        fire_after=2,
        clear_after=2,
    )
    values.update(overrides)
    return MonitorConfig(**values)


def batch(ages, plans, **extra) -> dict:
    return {"rows": [{"age": a, "plan": p, "prediction": 0.5, **extra} for a, p in zip(ages, plans, strict=True)]}


HEALTHY = batch(HEALTHY_AGES, HEALTHY_PLANS)
DRIFTED = batch(DRIFTED_AGES, DRIFTED_PLANS)


class FakeTimer:
    """Each call advances by ``step`` seconds, so one /ingest (two calls) always measures exactly ``step``."""

    def __init__(self, step: float = 0.03) -> None:
        self.now = 0.0
        self.step = step

    def __call__(self) -> float:
        self.now += self.step
        return self.now


@pytest.fixture
def config() -> MonitorConfig:
    return make_config()


@pytest.fixture
def client(config) -> TestClient:
    return TestClient(create_app(config, timer=FakeTimer()))


def scrape(client: TestClient) -> dict[tuple[str, tuple[tuple[str, str], ...]], float]:
    """Parse /metrics with prometheus_client's own parser: {(sample_name, sorted labels): value}."""
    response = client.get("/metrics")
    assert response.status_code == 200, response.text
    samples = {}
    for family in text_string_to_metric_families(response.text):
        for sample in family.samples:
            samples[(sample.name, tuple(sorted(sample.labels.items())))] = sample.value
    return samples
