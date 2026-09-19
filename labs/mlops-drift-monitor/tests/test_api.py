"""The FastAPI service: /ingest, /status, /metrics."""

from __future__ import annotations

import pytest
from conftest import DRIFTED, HEALTHY, FakeTimer, batch, make_config, scrape
from fastapi.testclient import TestClient

from lab.app import create_app


def psi_gauge(client, feature="age"):
    return scrape(client).get(("drift_feature_psi", (("feature", feature),)))


def test_ingest_accepts_a_batch_and_reports_the_window_state(client):
    small = {"rows": HEALTHY["rows"][:6]}
    response = client.post("/ingest", json=small)
    assert response.status_code == 200
    assert response.json() == {"accepted": 6, "window_rows": 6, "evaluated": False, "alerting": []}, (
        "below min_window_rows nothing is evaluated yet"
    )
    response = client.post("/ingest", json={"rows": HEALTHY["rows"][:8]})
    assert response.json()["window_rows"] == 14 and response.json()["evaluated"] is True


def test_ingest_rejects_bad_batches_with_422_and_changes_nothing(client):
    good = HEALTHY["rows"]
    bad_bodies = {
        "empty rows": {"rows": []},
        "no rows key": {},
        "rows not a list": {"rows": "abc"},
        "missing feature": {"rows": [{"age": 30.0}]},
        "null feature": {"rows": [{"age": None, "plan": "free"}]},
        "string in numeric feature": {"rows": [{"age": "old", "plan": "free"}]},
        "boolean in numeric feature": {"rows": [{"age": True, "plan": "free"}]},
        "bad row after good rows": {"rows": good + [{"age": 40.0}]},
    }
    for label, body in bad_bodies.items():
        response = client.post("/ingest", json=body)
        assert response.status_code == 422, f"{label}: expected 422, got {response.status_code}"
    detail = client.post("/ingest", json={"rows": good + [{"age": 40.0}]}).json()["detail"]
    assert "row 20" in str(detail) and "plan" in str(detail), "the error must say which row and feature"

    status = client.get("/status").json()
    assert status["window_rows"] == 0, "a rejected batch must not be partially ingested"
    assert scrape(client).get(("drift_ingested_rows_total", ())) in (None, 0.0), "and must not be counted"


def test_extra_columns_such_as_prediction_are_accepted(client):
    response = client.post("/ingest", json=batch([30.0] * 12, ["free"] * 12, prediction=0.93, model_version="v7"))
    assert response.status_code == 200 and response.json()["accepted"] == 12


def test_status_before_enough_data_reports_not_ready_and_no_recommendation(client):
    body = client.get("/status").json()
    assert body["ready"] is False and body["features"] == {} and body["alerting"] == []
    assert body["recommendation"]["action"] == "none"


def test_status_reports_per_feature_statistics_for_a_healthy_window(client):
    client.post("/ingest", json=HEALTHY)
    body = client.get("/status").json()
    assert body["ready"] is True and body["window_rows"] == 20
    age, plan = body["features"]["age"], body["features"]["plan"]
    assert age["kind"] == "numeric" and 0 <= age["psi"] < 0.1
    assert 0 <= age["ks_statistic"] < 0.3 and age["ks_pvalue"] > 0.05
    assert plan["kind"] == "categorical" and plan["chi2_pvalue"] > 0.5
    assert not age["breached"] and not plan["breached"]
    assert body["recommendation"] == {"action": "none", "reasons": []}

    client.post("/ingest", json=DRIFTED)  # the window is replaced: status must describe the NEW window
    later = client.get("/status").json()["features"]["age"]
    assert later["psi"] > 0.3 and later["breached"] is True, "status must always reflect the latest evaluation"


def test_alert_uses_hysteresis_fires_on_the_second_consecutive_drifted_window_and_clears_after_two_healthy(client):
    first = client.post("/ingest", json=DRIFTED).json()
    assert first["alerting"] == [], "one drifted window is not enough to fire (fire_after=2)"
    assert client.get("/status").json()["features"]["age"]["breached"] is True
    assert client.post("/ingest", json=DRIFTED).json()["alerting"] == ["age", "plan"]

    assert client.post("/ingest", json=HEALTHY).json()["alerting"] == ["age", "plan"], "still firing after 1 healthy window"
    assert client.post("/ingest", json=HEALTHY).json()["alerting"] == [], "cleared after 2 healthy windows"
    assert client.get("/status").json()["recommendation"]["action"] == "none"


def test_retrain_recommendation_when_several_features_or_a_critical_psi_are_firing(client):
    for _ in range(2):
        client.post("/ingest", json=DRIFTED)
    recommendation = client.get("/status").json()["recommendation"]
    assert recommendation["action"] == "retrain" and recommendation["reasons"]

    only_age = TestClient(create_app(make_config(psi_critical=0.3), timer=FakeTimer()))
    for _ in range(2):
        only_age.post("/ingest", json=batch([65.0 + i * 0.5 for i in range(20)], ["free"] * 12 + ["pro"] * 8))
    status = only_age.get("/status").json()
    assert status["alerting"] == ["age"]
    assert status["features"]["age"]["psi"] >= 0.3 and status["recommendation"]["action"] == "retrain"

    mild = TestClient(create_app(make_config(psi_critical=50.0), timer=FakeTimer()))
    for _ in range(2):
        mild.post("/ingest", json=batch([65.0 + i * 0.5 for i in range(20)], ["free"] * 12 + ["pro"] * 8))
    assert mild.get("/status").json()["recommendation"]["action"] == "investigate", "one non-critical alert: look, do not retrain"


def test_metrics_endpoint_is_valid_prometheus_text_with_the_expected_series(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "# TYPE drift_feature_psi gauge" in response.text
    assert "# TYPE drift_ingested_rows_total counter" in response.text or "# TYPE drift_ingested_rows counter" in response.text
    assert "# TYPE drift_ingest_latency_seconds histogram" in response.text


def test_psi_gauge_per_feature_alert_gauge_and_row_counter_track_ingestion(client):
    client.post("/ingest", json=HEALTHY)
    healthy_psi = psi_gauge(client)
    assert healthy_psi is not None and healthy_psi < 0.1
    assert psi_gauge(client, "plan") is None, "the PSI gauge only exists for numeric features"

    client.post("/ingest", json=DRIFTED)
    client.post("/ingest", json=DRIFTED)
    samples = scrape(client)
    assert samples[("drift_feature_psi", (("feature", "age"),))] > 0.3, "gauge follows the latest window"
    assert samples[("drift_ingested_rows_total", ())] == 60
    assert samples[("drift_feature_alert", (("feature", "age"),))] == 1
    assert samples[("drift_feature_alert", (("feature", "plan"),))] == 1


def test_ingest_latency_histogram_records_one_observation_per_request(client):
    for _ in range(3):
        client.post("/ingest", json=HEALTHY)
    client.post("/ingest", json={"rows": []})  # rejected: must not be observed
    samples = scrape(client)
    assert samples[("drift_ingest_latency_seconds_count", ())] == 3
    assert samples[("drift_ingest_latency_seconds_sum", ())] == pytest.approx(0.09)
    assert samples[("drift_ingest_latency_seconds_bucket", (("le", "0.05"),))] == 3
    assert samples[("drift_ingest_latency_seconds_bucket", (("le", "0.025"),))] == 0


def test_each_app_has_its_own_prometheus_registry_and_state():
    first = TestClient(create_app(make_config(), timer=FakeTimer()))
    second = TestClient(create_app(make_config(), timer=FakeTimer()))  # would raise "Duplicated timeseries" on a global registry
    first.post("/ingest", json=DRIFTED)
    assert scrape(first)[("drift_ingested_rows_total", ())] == 20
    assert scrape(second).get(("drift_ingested_rows_total", ()), 0.0) == 0.0
    assert second.get("/status").json()["window_rows"] == 0
