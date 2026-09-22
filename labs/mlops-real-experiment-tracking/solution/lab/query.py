"""Task 3: query real runs back from the tracking server and pick the best one."""

from __future__ import annotations

from mlflow.tracking import MlflowClient

from .config import RunSummary


def list_runs(tracking_uri: str, experiment_name: str) -> list[RunSummary]:
    """Return every run in ``experiment_name``, oldest first, as read back from the real server."""
    client = MlflowClient(tracking_uri=tracking_uri)
    experiment = client.get_experiment_by_name(experiment_name)
    if experiment is None:
        return []

    runs = client.search_runs(
        [experiment.experiment_id], order_by=["attribute.start_time ASC"]
    )
    return [
        RunSummary(
            run_id=run.info.run_id,
            params=dict(run.data.params),
            metrics=dict(run.data.metrics),
            start_time=run.info.start_time,
        )
        for run in runs
    ]


def best_run(
    tracking_uri: str,
    experiment_name: str,
    metric: str,
    *,
    higher_is_better: bool = True,
) -> RunSummary:
    """Return the run with the best value of ``metric`` among runs that logged it."""
    candidates = [r for r in list_runs(tracking_uri, experiment_name) if metric in r.metrics]
    if not candidates:
        raise ValueError(f"no run in {experiment_name!r} logged metric {metric!r}")

    sign = 1.0 if higher_is_better else -1.0

    def sort_key(run: RunSummary) -> tuple[float, int]:
        # Earliest start_time wins ties, regardless of search/registration order.
        return (sign * run.metrics[metric], -run.start_time)

    return max(candidates, key=sort_key)
