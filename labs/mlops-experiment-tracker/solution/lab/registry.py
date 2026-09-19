"""Model registry with stages, promotion gates, rollback and lineage (reference solution)."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from types import TracebackType

from lab.db import connect, from_iso, to_iso, utcnow
from lab.errors import (
    InvalidTransitionError,
    LineageError,
    ModelVersionNotFoundError,
    PromotionBlockedError,
    RegistryError,
    RollbackError,
)
from lab.models import GateResult, HistoryEvent, Lineage, ModelVersion, PromotionPolicy, RunStatus, Stage

EPSILON = 1e-9

ALLOWED_TRANSITIONS: dict[Stage, set[Stage]] = {
    Stage.NONE: {Stage.STAGING, Stage.ARCHIVED},
    Stage.STAGING: {Stage.PRODUCTION, Stage.ARCHIVED},
    Stage.PRODUCTION: {Stage.ARCHIVED},
    Stage.ARCHIVED: set(),  # terminal - only ``rollback`` may resurrect an archived version
}


def at_least(value: float, threshold: float) -> bool:
    """Float-safe ``value >= threshold``."""
    return value >= threshold - EPSILON


def meets_margin(candidate: float, baseline: float, margin: float, higher_is_better: bool = True) -> bool:
    """Does ``candidate`` beat ``baseline`` by at least ``margin`` (float-safe)?

    Naive ``0.938 - 0.933 >= 0.005`` is False because the subtraction gives 0.004999999999999893.
    """
    improvement = candidate - baseline if higher_is_better else baseline - candidate
    return improvement >= margin - EPSILON


class Registry:
    def __init__(self, db_path: str | Path, *, clock: Callable[[], datetime] = utcnow) -> None:
        self._conn = connect(db_path)
        self._clock = clock

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Registry:
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None:
        self.close()

    # ------------------------------------------------------------- helpers
    def _row(self, model: str, version: int) -> sqlite3.Row:
        row = self._conn.execute(
            "SELECT * FROM model_versions WHERE model = ? AND version = ?", (model, version)
        ).fetchone()
        if row is None:
            raise ModelVersionNotFoundError(f"{model} v{version} does not exist")
        return row

    @staticmethod
    def _to_version(row: sqlite3.Row) -> ModelVersion:
        return ModelVersion(
            model=row["model"],
            version=row["version"],
            run_id=row["run_id"],
            stage=Stage(row["stage"]),
            validated=bool(row["validated"]),
            created_at=from_iso(row["created_at"]),
        )

    def _final_metric(self, run_id: str, metric: str) -> float | None:
        row = self._conn.execute(
            "SELECT value FROM metrics WHERE run_id = ? AND key = ? ORDER BY step DESC LIMIT 1", (run_id, metric)
        ).fetchone()
        return None if row is None else row["value"]

    def _production_row(self, model: str) -> sqlite3.Row | None:
        return self._conn.execute(
            "SELECT * FROM model_versions WHERE model = ? AND stage = ?", (model, Stage.PRODUCTION.value)
        ).fetchone()

    def _set_stage(self, model: str, version: int, new_stage: Stage, reason: str) -> None:
        """Change a stage and write the audit row. Caller owns the transaction."""
        old = self._row(model, version)["stage"]
        self._conn.execute(
            "UPDATE model_versions SET stage = ? WHERE model = ? AND version = ?", (new_stage.value, model, version)
        )
        self._conn.execute(
            "INSERT INTO stage_history (model, version, from_stage, to_stage, reason, at) VALUES (?, ?, ?, ?, ?, ?)",
            (model, version, old, new_stage.value, reason, to_iso(self._clock())),
        )

    # ------------------------------------------------------------- versions
    def register_version(self, model: str, run_id: str) -> int:
        run = self._conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if run is None:
            raise RegistryError(f"run {run_id!r} does not exist")
        if run["status"] != RunStatus.FINISHED.value:
            raise RegistryError(f"run {run_id!r} is {run['status']}; only FINISHED runs can be registered")
        missing = [name for name in ("dataset_hash", "code_version") if not run[name]]
        if missing:
            raise LineageError(f"run {run_id!r} has no {' / '.join(missing)}; models must be reproducible")
        with self._conn:
            latest = self._conn.execute(
                "SELECT COALESCE(MAX(version), 0) AS v FROM model_versions WHERE model = ?", (model,)
            ).fetchone()["v"]
            self._conn.execute(
                "INSERT INTO model_versions (model, version, run_id, stage, validated, created_at) VALUES (?, ?, ?, ?, 0, ?)",
                (model, latest + 1, run_id, Stage.NONE.value, to_iso(self._clock())),
            )
        return latest + 1

    def get_version(self, model: str, version: int) -> ModelVersion:
        return self._to_version(self._row(model, version))

    def list_versions(self, model: str) -> list[ModelVersion]:
        rows = self._conn.execute("SELECT * FROM model_versions WHERE model = ? ORDER BY version", (model,))
        return [self._to_version(r) for r in rows]

    def latest(self, model: str, stage: Stage) -> int | None:
        """Highest version number currently in ``stage`` (or None)."""
        row = self._conn.execute(
            "SELECT MAX(version) AS v FROM model_versions WHERE model = ? AND stage = ?", (model, stage.value)
        ).fetchone()
        return row["v"]

    def history(self, model: str) -> list[HistoryEvent]:
        rows = self._conn.execute("SELECT * FROM stage_history WHERE model = ? ORDER BY seq", (model,))
        return [
            HistoryEvent(r["seq"], r["model"], r["version"], Stage(r["from_stage"]), Stage(r["to_stage"]), r["reason"], from_iso(r["at"]))
            for r in rows
        ]

    def lineage(self, model: str, version: int) -> Lineage:
        row = self._row(model, version)
        run = self._conn.execute("SELECT * FROM runs WHERE run_id = ?", (row["run_id"],)).fetchone()
        params = {r["key"]: r["value"] for r in self._conn.execute("SELECT key, value FROM params WHERE run_id = ?", (row["run_id"],))}
        artifacts = {r["name"]: r["sha256"] for r in self._conn.execute("SELECT name, sha256 FROM artifacts WHERE run_id = ?", (row["run_id"],))}
        return Lineage(model, version, row["run_id"], run["dataset_hash"], run["code_version"], params, artifacts)

    # ------------------------------------------------------------- quality signals
    def mark_validated(self, model: str, version: int, validated: bool = True) -> None:
        self._row(model, version)
        with self._conn:
            self._conn.execute(
                "UPDATE model_versions SET validated = ? WHERE model = ? AND version = ?", (int(validated), model, version)
            )

    def add_quality_flag(self, model: str, version: int, description: str) -> int:
        self._row(model, version)
        with self._conn:
            cursor = self._conn.execute(
                "INSERT INTO quality_flags (model, version, description, created_at) VALUES (?, ?, ?, ?)",
                (model, version, description, to_iso(self._clock())),
            )
        return int(cursor.lastrowid)

    def resolve_quality_flag(self, flag_id: int) -> None:
        with self._conn:
            cursor = self._conn.execute(
                "UPDATE quality_flags SET status = 'resolved', resolved_at = ? WHERE flag_id = ? AND status = 'open'",
                (to_iso(self._clock()), flag_id),
            )
        if cursor.rowcount == 0:
            raise RegistryError(f"no open quality flag with id {flag_id}")

    def open_quality_flags(self, model: str, version: int) -> list[str]:
        rows = self._conn.execute(
            "SELECT description FROM quality_flags WHERE model = ? AND version = ? AND status = 'open' ORDER BY flag_id",
            (model, version),
        )
        return [r["description"] for r in rows]

    # ------------------------------------------------------------- gates + transitions
    def check_promotion(self, model: str, version: int, policy: PromotionPolicy) -> GateResult:
        row = self._row(model, version)
        reasons: list[str] = []
        value = self._final_metric(row["run_id"], policy.metric)
        if value is None:
            reasons.append(f"run {row['run_id']} has no metric {policy.metric!r}")
        else:
            passes = at_least(value, policy.threshold) if policy.higher_is_better else at_least(policy.threshold, value)
            if not passes:
                bound = ">=" if policy.higher_is_better else "<="
                reasons.append(f"{policy.metric}={value} does not meet threshold {bound} {policy.threshold}")
            production = self._production_row(model)
            if production is not None and production["version"] != version:
                baseline = self._final_metric(production["run_id"], policy.metric)
                if baseline is not None and not meets_margin(value, baseline, policy.min_improvement, policy.higher_is_better):
                    reasons.append(
                        f"{policy.metric}={value} must beat production v{production['version']} ({baseline}) "
                        f"by at least {policy.min_improvement} (margin not met)"
                    )
        if policy.require_validated and not row["validated"]:
            reasons.append("version has not been marked validated")
        open_flags = self.open_quality_flags(model, version)
        if open_flags:
            reasons.append(f"{len(open_flags)} open data-quality flag(s): {'; '.join(open_flags)}")
        return GateResult(passed=not reasons, reasons=reasons)

    def transition(
        self,
        model: str,
        version: int,
        to_stage: Stage,
        *,
        policy: PromotionPolicy | None = None,
        reason: str = "",
    ) -> None:
        row = self._row(model, version)
        current = Stage(row["stage"])
        if to_stage not in ALLOWED_TRANSITIONS[current]:
            raise InvalidTransitionError(f"{model} v{version}: cannot go from {current.value} to {to_stage.value}")
        if to_stage is Stage.PRODUCTION:
            if policy is None:
                raise ValueError("promotion to Production requires a PromotionPolicy")
            result = self.check_promotion(model, version, policy)
            if not result.passed:
                raise PromotionBlockedError(result.reasons)
        with self._conn:  # one transaction: never two Production versions, never a half-done promotion
            if to_stage is Stage.PRODUCTION:
                old = self._production_row(model)
                if old is not None:
                    self._set_stage(model, old["version"], Stage.ARCHIVED, f"superseded by v{version}")
            self._set_stage(model, version, to_stage, reason)

    def rollback(self, model: str, *, reason: str = "") -> int:
        """Archive the current Production version and restore the one it superseded. Returns the restored version.

        Emergency operation: promotion gates are NOT re-checked.
        """
        current = self._production_row(model)
        if current is None:
            raise RollbackError(f"{model} has no Production version to roll back")
        events = [e for e in self.history(model) if e.to_stage is Stage.PRODUCTION]
        current_since = max(e.seq for e in events if e.version == current["version"])
        earlier = [e for e in events if e.seq < current_since and e.version != current["version"]]
        if not earlier:
            raise RollbackError(f"{model} v{current['version']} is the only version ever in Production; nothing to restore")
        target = max(earlier, key=lambda e: e.seq).version
        with self._conn:
            self._set_stage(model, current["version"], Stage.ARCHIVED, f"rollback: {reason}".strip())
            self._set_stage(model, target, Stage.PRODUCTION, f"rollback restore: {reason}".strip())
        return target
