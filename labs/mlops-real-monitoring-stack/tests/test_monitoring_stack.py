"""Real assertions against the real, running docker-compose stack.

Every number here comes from actually hitting the real FastAPI app and actually querying the real
Prometheus HTTP API (`/api/v1/query`, `/api/v1/alerts`) - nothing is mocked or hand-computed. The
session-scoped `compose_stack` fixture (see conftest.py) brings the stack up before the first test
and tears it down (docker compose down -v) after the last one, whether they passed or not.
"""

from __future__ import annotations

import time

import requests


def wait_until(predicate, timeout: float, interval: float = 1.0, description: str = "condition") -> None:
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            if predicate():
                return
        except Exception as exc:  # noqa: BLE001 - keep polling, surface the last error on timeout
            last_error = exc
        time.sleep(interval)
    raise TimeoutError(f"timed out after {timeout}s waiting for: {description} (last error: {last_error})")


# The sandbox this runs in has only 2 CPU cores shared between the app, Prometheus, Grafana and the
# test process itself; under load a "fast" request can occasionally take a few seconds of wall time
# even though it does almost no work, so every HTTP call here uses a generous timeout on purpose -
# this is host contention, not something the alerting logic under test needs to tolerate.
HTTP_TIMEOUT = 20


def prom_instant_value(prometheus_url: str, expr: str) -> float | None:
    resp = requests.get(f"{prometheus_url}/api/v1/query", params={"query": expr}, timeout=HTTP_TIMEOUT).json()
    result = resp["data"]["result"]
    if not result:
        return None
    return float(result[0]["value"][1])


def alert_state(prometheus_url: str, alert_name: str) -> str | None:
    resp = requests.get(f"{prometheus_url}/api/v1/alerts", timeout=HTTP_TIMEOUT).json()
    for alert in resp.get("data", {}).get("alerts", []):
        if alert.get("labels", {}).get("alertname") == alert_name:
            return alert.get("state")
    return None


def test_prometheus_target_is_up(compose_stack):
    resp = requests.get(f"{compose_stack['prometheus']}/api/v1/targets", timeout=5).json()
    active = resp["data"]["activeTargets"]
    app_targets = [t for t in active if t["labels"].get("job") == "fastapi-app"]
    assert app_targets, "prometheus has no 'fastapi-app' scrape target configured"
    assert app_targets[0]["health"] == "up", f"scrape target unhealthy: {app_targets[0]}"


def test_real_load_increments_real_counter_and_histogram(compose_stack):
    app_url = compose_stack["app"]
    prometheus_url = compose_stack["prometheus"]

    before = prom_instant_value(prometheus_url, 'http_requests_total{endpoint="/predict"}') or 0.0

    n_requests = 25
    for i in range(n_requests):
        r = requests.post(f"{app_url}/predict", json={"features": [0.1 * (i % 5), -0.05]}, timeout=HTTP_TIMEOUT)
        assert r.status_code == 200, r.text

    # Let Prometheus complete at least a couple of real scrapes (scrape_interval=2s in prometheus.yml).
    time.sleep(6)

    def scraped_enough() -> bool:
        after = prom_instant_value(prometheus_url, 'http_requests_total{endpoint="/predict"}')
        return after is not None and after >= before + n_requests

    wait_until(scraped_enough, timeout=30, interval=2, description="counter reflects the real load just sent")

    after_count = prom_instant_value(prometheus_url, 'http_requests_total{endpoint="/predict"}')
    after_hist_count = prom_instant_value(prometheus_url, 'http_request_duration_seconds_count{endpoint="/predict"}')

    assert after_count is not None and after_count >= before + n_requests, (
        f"expected http_requests_total{{endpoint='/predict'}} to grow by >= {n_requests}, "
        f"before={before} after={after_count}"
    )
    assert after_hist_count is not None and after_hist_count >= n_requests, (
        f"expected http_request_duration_seconds_count{{endpoint='/predict'}} >= {n_requests}, got {after_hist_count}"
    )


def test_real_latency_spike_fires_real_alert(compose_stack):
    app_url = compose_stack["app"]
    prometheus_url = compose_stack["prometheus"]

    assert alert_state(prometheus_url, "HighPredictRequestLatency") in (None, "inactive", "pending"), (
        "latency alert was already firing before this test induced any load"
    )

    window_seconds = 60
    deadline = time.monotonic() + window_seconds
    sent = 0
    while time.monotonic() < deadline:
        r = requests.post(
            f"{app_url}/predict",
            json={"features": [0.0], "simulate_latency_seconds": 1.2},
            timeout=HTTP_TIMEOUT,
        )
        assert r.status_code == 200, r.text
        sent += 1
        if alert_state(prometheus_url, "HighPredictRequestLatency") == "firing":
            break

    state = alert_state(prometheus_url, "HighPredictRequestLatency")
    assert state == "firing", (
        f"HighPredictRequestLatency never reached 'firing' after sending {sent} slow (~1.2s) real "
        f"requests over {window_seconds}s; last observed state={state}"
    )


def test_real_input_drift_fires_real_alert(compose_stack):
    app_url = compose_stack["app"]
    prometheus_url = compose_stack["prometheus"]

    r = requests.post(f"{app_url}/predict", json={"features": [100.0, 100.0, 100.0]}, timeout=HTTP_TIMEOUT)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["drift_score"] > 5, f"expected a real drift score > 5, got {body['drift_score']}"

    def drift_firing() -> bool:
        return alert_state(prometheus_url, "HighPredictionDrift") == "firing"

    wait_until(drift_firing, timeout=45, interval=2, description="HighPredictionDrift alert reaches 'firing'")
