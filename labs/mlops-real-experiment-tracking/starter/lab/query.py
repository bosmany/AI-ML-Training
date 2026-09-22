"""Task 3: query real runs back from the tracking server and pick the best one."""

from __future__ import annotations

from .config import RunSummary


def list_runs(tracking_uri: str, experiment_name: str) -> list[RunSummary]:
    """Return every run in ``experiment_name``, oldest first, as read back from the real server.

    Implement with ``mlflow.tracking.MlflowClient(tracking_uri=tracking_uri)``:

    1. ``client.get_experiment_by_name(experiment_name)`` - if it does not exist yet, return ``[]``.
    2. ``client.search_runs([experiment.experiment_id], order_by=["attribute.start_time ASC"])``.
    3. Map each real ``Run`` to a ``RunSummary`` (``run.info.run_id``, ``dict(run.data.params)``,
       ``dict(run.data.metrics)``, ``run.info.start_time``).
    """
    raise NotImplementedError


def best_run(
    tracking_uri: str,
    experiment_name: str,
    metric: str,
    *,
    higher_is_better: bool = True,
) -> RunSummary:
    """Return the run with the best value of ``metric`` among runs that logged it.

    Implement on top of ``list_runs``:

    - Filter to runs whose ``metrics`` dict actually contains ``metric`` (a run that never logged it
      is not a candidate, not a 0).
    - If no run qualifies, raise ``ValueError`` with a message naming the metric.
    - Pick the best by ``metric`` (max if ``higher_is_better`` else min); break ties by the earliest
      ``start_time`` so the answer never depends on dict/registration order.
    """
    raise NotImplementedError
