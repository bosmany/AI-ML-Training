"""Comparing and selecting real runs, cross-checked against the raw REST API."""

from __future__ import annotations

import pytest
import requests
from mlflow.tracking import MlflowClient

from lab import RunConfig, best_run, list_runs, train_and_log

SHALLOW = RunConfig(n_estimators=5, max_depth=1, random_state=42)
MID = RunConfig(n_estimators=50, max_depth=None, random_state=42)
DEEP = RunConfig(n_estimators=200, max_depth=None, random_state=42)


def test_list_runs_on_a_fresh_experiment_is_empty(mlflow_tracking_uri, experiment_name):
    assert list_runs(mlflow_tracking_uri, experiment_name) == []


def test_list_runs_returns_every_started_run_oldest_first(mlflow_tracking_uri, experiment_name):
    first = train_and_log(mlflow_tracking_uri, experiment_name, SHALLOW)
    second = train_and_log(mlflow_tracking_uri, experiment_name, DEEP)

    runs = list_runs(mlflow_tracking_uri, experiment_name)

    assert [r.run_id for r in runs] == [first.run_id, second.run_id]
    assert runs[0].params["n_estimators"] == "5"
    assert runs[1].params["n_estimators"] == "200"


def test_best_run_selects_the_highest_accuracy(mlflow_tracking_uri, experiment_name):
    shallow = train_and_log(mlflow_tracking_uri, experiment_name, SHALLOW)
    mid = train_and_log(mlflow_tracking_uri, experiment_name, MID)
    deep = train_and_log(mlflow_tracking_uri, experiment_name, DEEP)

    winner = best_run(mlflow_tracking_uri, experiment_name, "accuracy")

    assert winner.run_id == deep.run_id
    assert winner.metrics["accuracy"] == deep.accuracy
    assert deep.accuracy >= mid.accuracy >= shallow.accuracy


def test_best_run_with_lower_is_better_picks_the_same_winner_by_error_rate(
    mlflow_tracking_uri, experiment_name
):
    shallow = train_and_log(mlflow_tracking_uri, experiment_name, SHALLOW)
    deep = train_and_log(mlflow_tracking_uri, experiment_name, DEEP)

    by_accuracy = best_run(mlflow_tracking_uri, experiment_name, "accuracy", higher_is_better=True)
    by_error = best_run(
        mlflow_tracking_uri, experiment_name, "error_rate", higher_is_better=False
    )

    assert by_accuracy.run_id == deep.run_id
    assert by_error.run_id == deep.run_id
    assert by_accuracy.run_id == by_error.run_id
    assert shallow.run_id != deep.run_id  # sanity: the two configs really are different runs


def test_best_run_raises_for_a_metric_nothing_logged(mlflow_tracking_uri, experiment_name):
    train_and_log(mlflow_tracking_uri, experiment_name, SHALLOW)

    with pytest.raises(ValueError, match="never-logged"):
        best_run(mlflow_tracking_uri, experiment_name, "never-logged")


def test_list_runs_matches_the_raw_rest_api_search(mlflow_tracking_uri, experiment_name):
    """Independent check with `requests` against the real REST API - not the same code path as
    MlflowClient, so a bug that only exists in list_runs cannot hide behind it."""
    trained = train_and_log(mlflow_tracking_uri, experiment_name, MID)

    client = MlflowClient(tracking_uri=mlflow_tracking_uri)
    experiment = client.get_experiment_by_name(experiment_name)

    resp = requests.post(
        f"{mlflow_tracking_uri}/api/2.0/mlflow/runs/search",
        json={"experiment_ids": [experiment.experiment_id], "max_results": 10},
    )
    resp.raise_for_status()
    rest_runs = resp.json()["runs"]
    assert len(rest_runs) == 1
    rest_metrics = {m["key"]: m["value"] for m in rest_runs[0]["data"]["metrics"]}

    our_runs = list_runs(mlflow_tracking_uri, experiment_name)
    assert len(our_runs) == 1
    assert our_runs[0].run_id == rest_runs[0]["info"]["run_id"] == trained.run_id
    assert our_runs[0].metrics["accuracy"] == rest_metrics["accuracy"]
