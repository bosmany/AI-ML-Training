"""Experiment tracker (starter). Every public method below is a TODO - implement them with ``sqlite3``.

Use ``self._conn`` (opened by ``lab.db.connect``; rows are addressable by column name), ALWAYS with ``?``
parameters, and wrap writes in ``with self._conn:`` so they commit atomically. The schema is in ``lab/db.py``.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Literal

from lab.db import connect, utcnow  # noqa: F401  (to_iso / from_iso are handy too)
from lab.models import Comparison, Run

CHUNK_SIZE = 1024 * 1024  # hash files in 1 MiB chunks so a 10 GB artifact does not need 10 GB of RAM


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


class Tracker:
    def __init__(
        self,
        db_path: str | Path,
        *,
        clock: Callable[[], datetime] = utcnow,
        id_factory: Callable[[], str] = _new_id,
    ) -> None:
        """Open the database and remember ``clock`` (for timestamps) and ``id_factory`` (for run ids).

        TODO: ``self._conn = connect(db_path)``; store the clock and id factory. Tests inject fakes so no
        test ever sleeps or depends on random ids.
        """
        raise NotImplementedError("TODO: Tracker.__init__")

    def close(self) -> None:
        raise NotImplementedError("TODO: close the connection")

    def __enter__(self) -> Tracker:
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None:
        self.close()

    # ------------------------------------------------------------- lifecycle
    def start_run(
        self,
        experiment: str,
        *,
        name: str | None = None,
        dataset_hash: str | None = None,
        code_version: str | None = None,
    ) -> str:
        """Create a RUNNING run and return its id.

        TODO: blank ``experiment`` -> ``ValueError``. ``run_id = self._new_id()``; ``start_time`` from the clock,
        stored with ``to_iso``. dataset_hash / code_version are the run's lineage (used by the registry).
        """
        raise NotImplementedError("TODO: start_run")

    def end_run(self, run_id: str, status: Literal["FINISHED", "FAILED"] = "FINISHED") -> None:
        """Mark the run FINISHED or FAILED and stamp ``end_time``.

        TODO: unknown run -> ``RunNotFoundError``; a run that is no longer RUNNING -> ``RunStateError`` (so ending
        twice fails). Ending as RUNNING is a ``ValueError``.
        """
        raise NotImplementedError("TODO: end_run")

    # ------------------------------------------------------------- logging (all need a RUNNING run)
    def log_param(self, run_id: str, key: str, value: object) -> None:
        """Store ``str(value)``. Params are IMMUTABLE.

        TODO: unknown run -> ``RunNotFoundError``; non-RUNNING run -> ``RunStateError``; empty key -> ``ValueError``.
        Logging the same key again with the same text is a no-op; with a different text raise
        ``ImmutableParamError`` and keep the original.
        """
        raise NotImplementedError("TODO: log_param")

    def log_metric(self, run_id: str, key: str, value: float, step: int = 0) -> None:
        """Record ``value`` for ``(key, step)``.

        TODO: NaN / +-inf -> ``ValueError`` (they poison comparisons). The same (key, step) again REPLACES the value
        (``INSERT ... ON CONFLICT DO UPDATE``); different steps are all kept.
        """
        raise NotImplementedError("TODO: log_metric")

    def set_tag(self, run_id: str, key: str, value: str) -> None:
        """Upsert a tag (tags, unlike params, may be overwritten)."""
        raise NotImplementedError("TODO: set_tag")

    def log_artifact(self, run_id: str, path: str | Path, name: str | None = None) -> str:
        """Record the SHA-256 (hex) of the file, stream it in ``CHUNK_SIZE`` chunks, and return the digest.

        TODO: store under ``name`` (default: the file's base name) with its size; logging the same name again
        replaces the row (no duplicates). A missing file raises ``FileNotFoundError`` and records nothing.
        """
        raise NotImplementedError("TODO: log_artifact")

    # ------------------------------------------------------------- reading
    def get_run(self, run_id: str) -> Run:
        """Assemble a ``Run`` (see lab/models.py): params, tags, artifacts, and the FINAL value of each metric.

        TODO: "final" = the value at the HIGHEST step (not the last one written, not the best one). Unknown run ->
        ``RunNotFoundError``. Convert stored ISO strings back with ``from_iso`` and the status with ``RunStatus``.
        """
        raise NotImplementedError("TODO: get_run")

    def metric_history(self, run_id: str, key: str) -> list[tuple[int, float]]:
        """``(step, value)`` pairs ordered by step."""
        raise NotImplementedError("TODO: metric_history")

    def list_runs(self, experiment: str) -> list[str]:
        """Run ids of an experiment ordered by (start_time, run_id)."""
        raise NotImplementedError("TODO: list_runs")

    # ------------------------------------------------------------- analysis
    def compare_runs(self, run_ids: list[str], metrics: list[str] | None = None) -> Comparison:
        """Side-by-side view of runs.

        TODO: ``metrics[run_id][key]`` = final value or None when the run never logged that key (``metrics=None``
        means "every key any run logged", sorted). ``differing_params[key][run_id]`` only for params whose values are
        NOT identical across all the runs (a param missing in one run counts as None, hence different).
        """
        raise NotImplementedError("TODO: compare_runs")

    def best_run(self, experiment: str, metric: str, *, mode: Literal["max", "min"] = "max") -> str | None:
        """Id of the best FINISHED run by its FINAL value of ``metric``, or None if there is no candidate.

        TODO: ignore RUNNING/FAILED runs and runs without the metric. Ties must be deterministic: earliest
        ``start_time`` first, then the lowest ``run_id``. Compare values rounded to 12 decimals so floating-point
        noise (0.5 vs 0.5 + 1e-15) is a tie, not a winner. Invalid ``mode`` -> ``ValueError``.
        """
        raise NotImplementedError("TODO: best_run")
