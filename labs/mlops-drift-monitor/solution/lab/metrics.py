"""Prometheus metrics with a per-instance registry (reference solution)."""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, generate_latest

from lab.schemas import FeatureDrift

DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)


class DriftMetrics:
    def __init__(self, registry: CollectorRegistry | None = None, *, buckets: tuple[float, ...] = DEFAULT_BUCKETS) -> None:
        # A fresh registry per instance: the default global registry would raise "Duplicated timeseries" the
        # second time an app is created in the same process (every test after the first).
        self.registry = registry or CollectorRegistry()
        self.psi = Gauge("drift_feature_psi", "Population Stability Index of a numeric feature", ["feature"], registry=self.registry)
        self.alert = Gauge("drift_feature_alert", "1 while the drift alert of a feature is firing", ["feature"], registry=self.registry)
        self.rows = Counter("drift_ingested_rows", "Rows ingested", registry=self.registry)  # exposed as ..._total
        self.latency = Histogram("drift_ingest_latency_seconds", "Time to handle one ingest request", buckets=buckets, registry=self.registry)

    def observe_ingest(self, rows: int, seconds: float) -> None:
        self.rows.inc(rows)
        self.latency.observe(seconds)

    def update_features(self, results: dict[str, FeatureDrift]) -> None:
        for name, result in results.items():
            if result.psi is not None:
                self.psi.labels(feature=name).set(result.psi)
            self.alert.labels(feature=name).set(1 if result.alerting else 0)

    def render(self) -> tuple[bytes, str]:
        """``(body, content_type)`` for the ``/metrics`` endpoint."""
        return generate_latest(self.registry), CONTENT_TYPE_LATEST
