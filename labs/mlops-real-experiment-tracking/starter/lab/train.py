"""Task 1: train a real model and log it to a real, running MLflow tracking server."""

from __future__ import annotations

from .config import RunConfig, TrainedRun


def train_and_log(tracking_uri: str, experiment_name: str, config: RunConfig) -> TrainedRun:
    """Train a ``RandomForestClassifier`` on ``lab.data.load_dataset()`` and log a real MLflow run.

    Implement, against the real MLflow server at ``tracking_uri`` (an HTTP tracking server, not the
    no-op default client):

    1. ``mlflow.set_tracking_uri(tracking_uri)`` then ``mlflow.set_experiment(experiment_name)``
       (creates the experiment on the server the first time, reuses it after).
    2. Load the data with ``load_dataset(random_state=config.random_state)``.
    3. ``with mlflow.start_run(...) as run:`` train a
       ``RandomForestClassifier(n_estimators=config.n_estimators, max_depth=config.max_depth,
       random_state=config.random_state)``, predict on the held-out test split, and compute
       ``accuracy_score`` and ``f1_score``.
    4. Inside the run: ``mlflow.log_param`` for every field of ``config``; ``mlflow.log_metric`` for
       ``accuracy``, ``f1`` and ``error_rate`` (``1 - accuracy`` - used later to test a "lower is
       better" query); ``mlflow.log_artifact`` a small JSON summary file (write it to a temp dir
       first, mlflow copies it); ``mlflow.sklearn.log_model(clf, name="model",
       serialization_format="pickle")`` (pickle, not the default ``skops`` format, or the model logs
       an ``UntrustedTypesFoundException`` for a ``RandomForestClassifier``).
    5. Return a ``TrainedRun`` built from the run's real id and the real metrics - do not recompute
       anything from local variables that the server was not actually given. For ``model_uri``, use
       the classic ``runs:/<run_id>/model`` scheme (the same one ``registry.py`` registers from) -
       do not use ``log_model()``'s own returned URI: on MLflow >= 3.0 it points at the newer
       ``models:/m-<id>`` "Logged Model" entity instead of the run.

    Raises whatever the real MLflow client raises (do not swallow errors).
    """
    raise NotImplementedError
