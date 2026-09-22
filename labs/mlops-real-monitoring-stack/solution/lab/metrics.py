"""Prometheus instrumentation for the model-serving app (reference solution).

Three real metrics, scraped by a real Prometheus container over HTTP:

- ``http_requests_total``            Counter,  labels: method, endpoint, status_code
- ``http_request_duration_seconds``  Histogram, labels: endpoint
- ``prediction_drift_score``         Gauge, no labels - the most recent |mean(features) - reference_mean|

The registry is module-level (one process = one app = one registry), which is fine here because,
unlike the pytest-only labs, this app only ever runs once per container - there is no "build a
second app in the same process" problem to work around.
"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

# Buckets span sub-10ms up to several seconds so a real induced latency spike (~1-2s) lands cleanly
# above the smaller buckets, which is what lets a p95 histogram_quantile() alert fire on real data.
LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0)

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests received",
    ["method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["endpoint"],
    buckets=LATENCY_BUCKETS,
)

PREDICTION_DRIFT = Gauge(
    "prediction_drift_score",
    "Absolute distance between the current request's mean feature value and the training-time reference mean",
)


def record_request(method: str, endpoint: str, status_code: int, duration_seconds: float) -> None:
    """Record one completed HTTP request. Called once per request by the ASGI middleware."""
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status_code=str(status_code)).inc()
    REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration_seconds)


def update_drift(features: list[float], reference_mean: float) -> float:
    """Compute and publish the drift gauge for one /predict call. Returns the score that was set."""
    if not features:
        score = abs(0.0 - reference_mean)
    else:
        score = abs((sum(features) / len(features)) - reference_mean)
    PREDICTION_DRIFT.set(score)
    return score


def render_latest() -> tuple[bytes, str]:
    """``(body, content_type)`` for the ``/metrics`` endpoint."""
    return generate_latest(), CONTENT_TYPE_LATEST
