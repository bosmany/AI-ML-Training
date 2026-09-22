"""Task 2: register a model from a run and promote it through the real Model Registry stage machine."""

from __future__ import annotations

from .config import PromotedVersion


def register_and_promote(
    tracking_uri: str,
    model_name: str,
    run_id: str,
    model_subpath: str = "model",
) -> PromotedVersion:
    """Register the model logged at ``runs:/<run_id>/<model_subpath>`` and promote it to Production.

    Implement, against the real Model Registry API on the server at ``tracking_uri``:

    1. ``mlflow.set_tracking_uri(tracking_uri)``.
    2. ``mlflow.register_model(f"runs:/{run_id}/{model_subpath}", model_name)`` - this creates the
       registered model the first time it is called for a given ``model_name`` and a new version
       every time after. Let a bad ``run_id`` raise the real ``MlflowException`` from the server.
    3. Using ``mlflow.tracking.MlflowClient``, ``transition_model_version_stage`` the new version to
       ``"Staging"``, then to ``"Production"`` with ``archive_existing_versions=True`` (this is what
       atomically archives whatever version was in Production before - do not archive it yourself).
    4. Read the version back from the server (``client.get_model_version``) and return a
       ``PromotedVersion`` built from that real response, not from what you think the stage should be.
    """
    raise NotImplementedError
