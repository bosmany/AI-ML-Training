"""Task 2: register a model from a run and promote it through the real Model Registry stage machine."""

from __future__ import annotations

import mlflow
from mlflow.tracking import MlflowClient

from .config import PromotedVersion


def register_and_promote(
    tracking_uri: str,
    model_name: str,
    run_id: str,
    model_subpath: str = "model",
) -> PromotedVersion:
    """Register the model logged at ``runs:/<run_id>/<model_subpath>`` and promote it to Production."""
    mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient(tracking_uri=tracking_uri)

    model_uri = f"runs:/{run_id}/{model_subpath}"
    model_version = mlflow.register_model(model_uri, model_name)

    client.transition_model_version_stage(
        name=model_name, version=model_version.version, stage="Staging"
    )
    client.transition_model_version_stage(
        name=model_name,
        version=model_version.version,
        stage="Production",
        archive_existing_versions=True,
    )

    real_version = client.get_model_version(model_name, model_version.version)
    return PromotedVersion(
        name=model_name,
        version=str(real_version.version),
        run_id=real_version.run_id,
        stage=real_version.current_stage,
    )
