"""Task 1: train a real model and log it to a real, running MLflow tracking server."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import mlflow
import mlflow.sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score

from .config import RunConfig, TrainedRun
from .data import load_dataset


def train_and_log(tracking_uri: str, experiment_name: str, config: RunConfig) -> TrainedRun:
    """Train a ``RandomForestClassifier`` on ``lab.data.load_dataset()`` and log a real MLflow run."""
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)

    X_train, X_test, y_train, y_test = load_dataset(random_state=config.random_state)

    run_name = f"rf-n{config.n_estimators}-d{config.max_depth}"
    with mlflow.start_run(run_name=run_name) as run:
        clf = RandomForestClassifier(
            n_estimators=config.n_estimators,
            max_depth=config.max_depth,
            random_state=config.random_state,
        )
        clf.fit(X_train, y_train)
        preds = clf.predict(X_test)
        accuracy = float(accuracy_score(y_test, preds))
        f1 = float(f1_score(y_test, preds))
        error_rate = 1.0 - accuracy

        mlflow.log_param("n_estimators", config.n_estimators)
        mlflow.log_param("max_depth", config.max_depth)
        mlflow.log_param("random_state", config.random_state)
        mlflow.log_metric("accuracy", accuracy)
        mlflow.log_metric("f1", f1)
        mlflow.log_metric("error_rate", error_rate)

        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "summary.json"
            summary_path.write_text(
                json.dumps(
                    {
                        "n_estimators": config.n_estimators,
                        "max_depth": config.max_depth,
                        "accuracy": accuracy,
                        "f1": f1,
                    },
                    indent=2,
                )
            )
            mlflow.log_artifact(str(summary_path), artifact_path="summary")

        mlflow.sklearn.log_model(clf, name="model", serialization_format="pickle")
        run_id = run.info.run_id

    return TrainedRun(
        run_id=run_id,
        accuracy=accuracy,
        f1=f1,
        error_rate=error_rate,
        # MLflow >= 3.0's `log_model()` returns a `models:/m-<id>` "Logged Model" URI by default.
        # This lab (and `registry.py`) deliberately teaches the classic, run-scoped URI scheme,
        # which still resolves correctly against a real server and is what `register_model` is
        # given elsewhere in this lab.
        model_uri=f"runs:/{run_id}/model",
    )
