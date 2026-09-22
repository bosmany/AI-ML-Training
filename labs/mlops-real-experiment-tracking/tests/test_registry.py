"""Real Model Registry stage transitions against the live server, verified two ways: through
MlflowClient and through the raw REST API with `requests` (never mocked)."""

from __future__ import annotations

import pytest
import requests
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient

from lab import RunConfig, register_and_promote, train_and_log

CONFIG = RunConfig(n_estimators=10, max_depth=3, random_state=42)


def test_register_and_promote_reaches_production(
    mlflow_tracking_uri, experiment_name, model_name
):
    trained = train_and_log(mlflow_tracking_uri, experiment_name, CONFIG)

    promoted = register_and_promote(mlflow_tracking_uri, model_name, trained.run_id)

    assert promoted.name == model_name
    assert promoted.run_id == trained.run_id
    assert promoted.version == "1"
    assert promoted.stage == "Production"


def test_promotion_is_visible_on_the_server_via_mlflow_client(
    mlflow_tracking_uri, experiment_name, model_name
):
    trained = train_and_log(mlflow_tracking_uri, experiment_name, CONFIG)
    promoted = register_and_promote(mlflow_tracking_uri, model_name, trained.run_id)

    client = MlflowClient(tracking_uri=mlflow_tracking_uri)
    real_version = client.get_model_version(model_name, promoted.version)
    assert real_version.current_stage == "Production"
    assert real_version.run_id == trained.run_id


def test_promoting_a_second_version_archives_the_first(
    mlflow_tracking_uri, experiment_name, model_name
):
    first = train_and_log(mlflow_tracking_uri, experiment_name, CONFIG)
    register_and_promote(mlflow_tracking_uri, model_name, first.run_id)

    second = train_and_log(mlflow_tracking_uri, experiment_name, CONFIG)
    promoted_second = register_and_promote(mlflow_tracking_uri, model_name, second.run_id)

    client = MlflowClient(tracking_uri=mlflow_tracking_uri)
    first_version = client.get_model_version(model_name, "1")

    assert promoted_second.version == "2"
    assert promoted_second.stage == "Production"
    assert first_version.current_stage == "Archived"


def test_register_and_promote_rejects_an_unknown_run_id(mlflow_tracking_uri, model_name):
    with pytest.raises(MlflowException):
        register_and_promote(mlflow_tracking_uri, model_name, "does-not-exist")


def test_production_version_matches_the_raw_rest_api(
    mlflow_tracking_uri, experiment_name, model_name
):
    """Independent check with `requests` against the real REST API - no MlflowClient involved."""
    trained = train_and_log(mlflow_tracking_uri, experiment_name, CONFIG)
    promoted = register_and_promote(mlflow_tracking_uri, model_name, trained.run_id)

    resp = requests.get(
        f"{mlflow_tracking_uri}/api/2.0/mlflow/registered-models/get-latest-versions",
        params={"name": model_name},
    )
    resp.raise_for_status()
    versions = resp.json()["model_versions"]
    production = [v for v in versions if v["current_stage"] == "Production"]

    assert len(production) == 1
    assert production[0]["version"] == promoted.version
    assert production[0]["run_id"] == trained.run_id
