"""Prometheus metrics with a per-instance registry (starter)."""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, generate_latest  # noqa: F401

from lab.schemas import FeatureDrift

DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)


class DriftMetrics:
    def __init__(self, registry: CollectorRegistry | None = None, *, buckets: tuple[float, ...] = DEFAULT_BUCKETS) -> None:
        """Create the metrics on ``self.registry`` (a NEW ``CollectorRegistry()`` unless one is passed).

        TODO - exactly these names (tests scrape them):
        - ``Gauge("drift_feature_psi", ..., ["feature"])``          PSI of each numeric feature
        - ``Gauge("drift_feature_alert", ..., ["feature"])``        1 while that feature's alert is firing else 0
        - ``Counter("drift_ingested_rows", ...)``                   exposed as ``drift_ingested_rows_total``
        - ``Histogram("drift_ingest_latency_seconds", ..., buckets=buckets)``
        Pass ``registry=self.registry`` to every metric. Never use the global default registry: creating a second app
        in the same process would raise ``ValueError: Duplicated timeseries``.
        """
        raise NotImplementedError("TODO: DriftMetrics.__init__")

    def observe_ingest(self, rows: int, seconds: float) -> None:
        """Count the rows and record one latency observation."""
        raise NotImplementedError("TODO: observe_ingest")

    def update_features(self, results: dict[str, FeatureDrift]) -> None:
        """Set the PSI gauge for features that have a PSI, and the alert gauge (1/0) for every feature."""
        raise NotImplementedError("TODO: update_features")

    def render(self) -> tuple[bytes, str]:
        """``(body, content_type)``: ``generate_latest(self.registry)`` and ``CONTENT_TYPE_LATEST``."""
        raise NotImplementedError("TODO: render")
