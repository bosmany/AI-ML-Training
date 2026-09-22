"""Prometheus instrumentation for the model-serving app.

Implement three real metrics that a real Prometheus container will scrape over HTTP from /metrics:

- ``http_requests_total``            Counter,  labels: method, endpoint, status_code
- ``http_request_duration_seconds``  Histogram, labels: endpoint
- ``prediction_drift_score``         Gauge, no labels - the most recent |mean(features) - reference_mean|

Buckets span sub-10ms up to several seconds on purpose: a real induced latency spike (~1-2s) must land
cleanly above the smaller buckets so a p95 histogram_quantile() alert can fire on real scraped data.
"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0)

# TODO 1: declare REQUEST_COUNT as a Counter named "http_requests_total" with labels
#         ["method", "endpoint", "status_code"].
REQUEST_COUNT = None

# TODO 2: declare REQUEST_LATENCY as a Histogram named "http_request_duration_seconds" with label
#         ["endpoint"] and buckets=LATENCY_BUCKETS.
REQUEST_LATENCY = None

# TODO 3: declare PREDICTION_DRIFT as a Gauge named "prediction_drift_score" (no labels).
PREDICTION_DRIFT = None


def record_request(method: str, endpoint: str, status_code: int, duration_seconds: float) -> None:
    """Record one completed HTTP request. Called once per request by the ASGI middleware.

    TODO 4: increment REQUEST_COUNT.labels(method=method, endpoint=endpoint,
            status_code=str(status_code)) and observe duration_seconds on
            REQUEST_LATENCY.labels(endpoint=endpoint).
    """
    raise NotImplementedError


def update_drift(features: list[float], reference_mean: float) -> float:
    """Compute and publish the drift gauge for one /predict call. Returns the score that was set.

    TODO 5: score = abs(mean(features) - reference_mean) (treat an empty list as mean 0.0),
            set PREDICTION_DRIFT to that score, and return it.
    """
    raise NotImplementedError


def render_latest() -> tuple[bytes, str]:
    """``(body, content_type)`` for the ``/metrics`` endpoint.

    TODO 6: return generate_latest() paired with CONTENT_TYPE_LATEST.
    """
    raise NotImplementedError
