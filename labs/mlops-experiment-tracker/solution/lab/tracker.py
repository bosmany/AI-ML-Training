"""Experiment tracker (reference solution)."""

from __future__ import annotations

import hashlib
import math
import sqlite3
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Literal

from lab.db import connect, from_iso, to_iso, utcnow
from lab.errors import ImmutableParamError, RunNotFoundError, RunStateError
from lab.models import Comparison, Run, RunStatus

CHUNK_SIZE = 1024 * 1024


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
        self._conn = connect(db_path)
        self._clock = clock
        self._new_id = id_factory

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Tracker:
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None:
        self.close()

    # ------------------------------------------------------------- helpers
    def _run_row(self, run_id: str) -> sqlite3.Row:
        row = self._conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise RunNotFoundError(f"run {run_id!r} does not exist")
        return row

    def _active_run(self, run_id: str) -> sqlite3.Row:
        row = self._run_row(run_id)
        if row["status"] != RunStatus.RUNNING.value:
            raise RunStateError(f"run {run_id!r} is {row['status']}; it can no longer be modified")
        return row

    # ------------------------------------------------------------- lifecycle
    def start_run(
        self,
        experiment: str,
        *,
        name: str | None = None,
        dataset_hash: str | None = None,
        code_version: str | None = None,
    ) -> str:
        if not experiment.strip():
            raise ValueError("experiment name must not be empty")
        run_id = self._new_id()
        with self._conn:
            self._conn.execute(
                "INSERT INTO runs (run_id, experiment, name, status, start_time, dataset_hash, code_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (run_id, experiment, name, RunStatus.RUNNING.value, to_iso(self._clock()), dataset_hash, code_version),
            )
        return run_id

    def end_run(self, run_id: str, status: Literal["FINISHED", "FAILED"] = "FINISHED") -> None:
        self._active_run(run_id)
        final = RunStatus(status)
        if final is RunStatus.RUNNING:
            raise ValueError("a run can only end as FINISHED or FAILED")
        with self._conn:
            self._conn.execute(
                "UPDATE runs SET status = ?, end_time = ? WHERE run_id = ?", (final.value, to_iso(self._clock()), run_id)
            )

    # ------------------------------------------------------------- logging
    def log_param(self, run_id: str, key: str, value: object) -> None:
        self._active_run(run_id)
        if not key:
            raise ValueError("param key must not be empty")
        text = str(value)
        row = self._conn.execute("SELECT value FROM params WHERE run_id = ? AND key = ?", (run_id, key)).fetchone()
        if row is not None:
            if row["value"] != text:
                raise ImmutableParamError(
                    f"param {key!r} of run {run_id!r} is already {row['value']!r}; cannot change it to {text!r}"
                )
            return  # same value again: idempotent
        with self._conn:
            self._conn.execute("INSERT INTO params (run_id, key, value) VALUES (?, ?, ?)", (run_id, key, text))

    def log_metric(self, run_id: str, key: str, value: float, step: int = 0) -> None:
        self._active_run(run_id)
        if not key:
            raise ValueError("metric key must not be empty")
        if not math.isfinite(value):
            raise ValueError(f"metric {key!r} must be a finite number, got {value!r}")
        with self._conn:
            self._conn.execute(
                "INSERT INTO metrics (run_id, key, step, value) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(run_id, key, step) DO UPDATE SET value = excluded.value",
                (run_id, key, step, float(value)),
            )

    def set_tag(self, run_id: str, key: str, value: str) -> None:
        self._active_run(run_id)
        with self._conn:
            self._conn.execute(
                "INSERT INTO tags (run_id, key, value) VALUES (?, ?, ?) "
                "ON CONFLICT(run_id, key) DO UPDATE SET value = excluded.value",
                (run_id, key, value),
            )

    def log_artifact(self, run_id: str, path: str | Path, name: str | None = None) -> str:
        """Record a file's SHA-256 (streamed in chunks) under ``name`` (default: file name). Returns the hex digest."""
        self._active_run(run_id)
        source = Path(path)
        digest = hashlib.sha256()
        size = 0
        with source.open("rb") as handle:  # raises FileNotFoundError for a missing file
            while chunk := handle.read(CHUNK_SIZE):
                digest.update(chunk)
                size += len(chunk)
        with self._conn:
            self._conn.execute(
                "INSERT INTO artifacts (run_id, name, sha256, size_bytes) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(run_id, name) DO UPDATE SET sha256 = excluded.sha256, size_bytes = excluded.size_bytes",
                (run_id, name or source.name, digest.hexdigest(), size),
            )
        return digest.hexdigest()

    # ------------------------------------------------------------- reading
    def get_run(self, run_id: str) -> Run:
        row = self._run_row(run_id)
        pairs = lambda table: {  # noqa: E731
            r["key"]: r["value"] for r in self._conn.execute(f"SELECT key, value FROM {table} WHERE run_id = ?", (run_id,))
        }
        final_metrics = {
            r["key"]: r["value"]
            for r in self._conn.execute(
                "SELECT m.key, m.value FROM metrics m WHERE m.run_id = ? AND m.step = "
                "(SELECT MAX(step) FROM metrics WHERE run_id = m.run_id AND key = m.key)",
                (run_id,),
            )
        }
        artifacts = {
            r["name"]: r["sha256"] for r in self._conn.execute("SELECT name, sha256 FROM artifacts WHERE run_id = ?", (run_id,))
        }
        return Run(
            run_id=row["run_id"],
            experiment=row["experiment"],
            name=row["name"],
            status=RunStatus(row["status"]),
            start_time=from_iso(row["start_time"]),
            end_time=from_iso(row["end_time"]) if row["end_time"] else None,
            dataset_hash=row["dataset_hash"],
            code_version=row["code_version"],
            params=pairs("params"),
            tags=pairs("tags"),
            metrics=final_metrics,
            artifacts=artifacts,
        )

    def metric_history(self, run_id: str, key: str) -> list[tuple[int, float]]:
        """``(step, value)`` pairs ordered by step."""
        self._run_row(run_id)
        rows = self._conn.execute(
            "SELECT step, value FROM metrics WHERE run_id = ? AND key = ? ORDER BY step", (run_id, key)
        )
        return [(r["step"], r["value"]) for r in rows]

    def list_runs(self, experiment: str) -> list[str]:
        rows = self._conn.execute(
            "SELECT run_id FROM runs WHERE experiment = ? ORDER BY start_time, run_id", (experiment,)
        )
        return [r["run_id"] for r in rows]

    # ------------------------------------------------------------- analysis
    def compare_runs(self, run_ids: list[str], metrics: list[str] | None = None) -> Comparison:
        runs = [self.get_run(run_id) for run_id in run_ids]
        keys = metrics if metrics is not None else sorted({k for run in runs for k in run.metrics})
        metric_table = {run.run_id: {k: run.metrics.get(k) for k in keys} for run in runs}
        differing: dict[str, dict[str, str | None]] = {}
        for key in sorted({k for run in runs for k in run.params}):
            values = {run.run_id: run.params.get(key) for run in runs}
            if len(set(values.values())) > 1:
                differing[key] = values
        return Comparison(metric_table, differing)

    def best_run(self, experiment: str, metric: str, *, mode: Literal["max", "min"] = "max") -> str | None:
        """Best FINISHED run by the run's FINAL value of ``metric``.

        Deterministic: ties (values equal to 12 decimals) go to the earliest start_time, then the lowest run_id.
        """
        if mode not in ("max", "min"):
            raise ValueError("mode must be 'max' or 'min'")
        candidates = []
        for run_id in self.list_runs(experiment):
            run = self.get_run(run_id)
            if run.status is RunStatus.FINISHED and metric in run.metrics:
                value = round(run.metrics[metric], 12)
                candidates.append(((-value if mode == "max" else value), to_iso(run.start_time), run.run_id))
        return min(candidates)[2] if candidates else None
