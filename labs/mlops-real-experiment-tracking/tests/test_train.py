"""Real sklearn training logged to the real MLflow server started by conftest.py."""

from __future__ import annotations

import json
from pathlib import Path

from mlflow.tracking import MlflowClient

from lab import RunConfig, train_and_log

SHALLOW = RunConfig(n_estimators=5, max_depth=1, random_state=42)
DEEP = RunConfig(n_estimators=200, max_depth=None, random_state=42)


def test_train_and_log_returns_a_real_run_id_and_metrics(mlflow_tracking_uri, experiment_name):
    result = train_and_log(mlflow_tracking_uri, experiment_name, SHALLOW)

    assert result.run_id  # a real MLflow run id, not empty/None
    assert 0.0 <= result.accuracy <= 1.0
    assert 0.0 <= result.f1 <= 1.0
    assert result.error_rate == 1.0 - result.accuracy
    assert result.model_uri.startswith("runs:/")


def test_train_and_log_persists_params_and_metrics_on_the_server(
    mlflow_tracking_uri, experiment_name
):
    result = train_and_log(mlflow_tracking_uri, experiment_name, DEEP)

    client = MlflowClient(tracking_uri=mlflow_tracking_uri)
    real_run = client.get_run(result.run_id)  # fetched back from the server, not a local object

    assert real_run.data.params["n_estimators"] == "200"
    assert real_run.data.params["max_depth"] == "None"
    assert real_run.data.metrics["accuracy"] == result.accuracy
    assert real_run.data.metrics["f1"] == result.f1
    assert real_run.data.metrics["error_rate"] == result.error_rate
    assert real_run.info.status == "FINISHED"


def test_train_and_log_logs_a_downloadable_artifact(mlflow_tracking_uri, experiment_name, tmp_path):
    result = train_and_log(mlflow_tracking_uri, experiment_name, SHALLOW)

    client = MlflowClient(tracking_uri=mlflow_tracking_uri)
    artifacts = client.list_artifacts(result.run_id, path="summary")
    assert any(a.path == "summary/summary.json" for a in artifacts)

    local_path = client.download_artifacts(result.run_id, "summary/summary.json", str(tmp_path))
    summary = json.loads(Path(local_path).read_text())
    assert summary["n_estimators"] == SHALLOW.n_estimators
    assert summary["accuracy"] == result.accuracy


def test_deeper_forest_beats_a_depth_capped_forest_on_this_dataset(
    mlflow_tracking_uri, experiment_name
):
    """A real ML claim, not a mock: on this fixed split, an unconstrained 200-tree forest is more
    accurate than a 5-tree forest capped at depth 1 - this is what the query tests will later sort
    on, so it is asserted directly here first."""
    shallow = train_and_log(mlflow_tracking_uri, experiment_name, SHALLOW)
    deep = train_and_log(mlflow_tracking_uri, experiment_name, DEEP)

    assert deep.accuracy > shallow.accuracy


def test_train_and_log_reuses_the_same_experiment_across_calls(
    mlflow_tracking_uri, experiment_name
):
    train_and_log(mlflow_tracking_uri, experiment_name, SHALLOW)
    train_and_log(mlflow_tracking_uri, experiment_name, DEEP)

    client = MlflowClient(tracking_uri=mlflow_tracking_uri)
    experiment = client.get_experiment_by_name(experiment_name)
    runs = client.search_runs([experiment.experiment_id])
    assert len(runs) == 2
