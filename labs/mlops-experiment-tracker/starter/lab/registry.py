"""Model registry with stages, promotion gates, rollback and lineage (starter). All TODO."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from types import TracebackType

from lab.db import connect, utcnow  # noqa: F401
from lab.models import GateResult, HistoryEvent, Lineage, ModelVersion, PromotionPolicy, Stage

EPSILON = 1e-9

# TODO: the legal moves. None -> Staging | Archived; Staging -> Production | Archived; Production -> Archived;
# Archived -> nothing (terminal - only ``rollback`` may bring an archived version back).
ALLOWED_TRANSITIONS: dict[Stage, set[Stage]] = {}


def at_least(value: float, threshold: float) -> bool:
    """Float-safe ``value >= threshold``.

    TODO: ``value >= threshold - EPSILON`` so 0.1 + 0.2 (0.30000000000000004) meets 0.3.
    """
    raise NotImplementedError("TODO: at_least")


def meets_margin(candidate: float, baseline: float, margin: float, higher_is_better: bool = True) -> bool:
    """Does ``candidate`` beat ``baseline`` by at least ``margin``?

    TODO: improvement = candidate - baseline (or baseline - candidate when lower is better); compare
    ``improvement >= margin - EPSILON``. Careful: ``0.938 - 0.933`` is 0.004999999999999893 in floating point, so a
    naive ``>= 0.005`` wrongly says "not enough".
    """
    raise NotImplementedError("TODO: meets_margin")


class Registry:
    def __init__(self, db_path: str | Path, *, clock: Callable[[], datetime] = utcnow) -> None:
        """TODO: ``self._conn = connect(db_path)`` and keep the clock."""
        raise NotImplementedError("TODO: Registry.__init__")

    def close(self) -> None:
        raise NotImplementedError("TODO: close")

    def __enter__(self) -> Registry:
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None:
        self.close()

    # ------------------------------------------------------------- versions
    def register_version(self, model: str, run_id: str) -> int:
        """Create the next version (1, 2, ... per model) in stage None and return its number.

        TODO: unknown run or run not FINISHED -> ``RegistryError``; run without dataset_hash or code_version ->
        ``LineageError`` (an unreproducible model must not enter the registry). Failures leave no row behind.
        """
        raise NotImplementedError("TODO: register_version")

    def get_version(self, model: str, version: int) -> ModelVersion:
        """TODO: unknown -> ``ModelVersionNotFoundError``."""
        raise NotImplementedError("TODO: get_version")

    def list_versions(self, model: str) -> list[ModelVersion]:
        """All versions of ``model`` ordered by version number."""
        raise NotImplementedError("TODO: list_versions")

    def latest(self, model: str, stage: Stage) -> int | None:
        """Highest version number currently in ``stage``, or None."""
        raise NotImplementedError("TODO: latest")

    def history(self, model: str) -> list[HistoryEvent]:
        """Every stage change of ``model`` ordered by ``seq`` (table ``stage_history``)."""
        raise NotImplementedError("TODO: history")

    def lineage(self, model: str, version: int) -> Lineage:
        """Where did this model come from? run id, dataset hash, code version, params, artifact hashes."""
        raise NotImplementedError("TODO: lineage")

    # ------------------------------------------------------------- quality signals
    def mark_validated(self, model: str, version: int, validated: bool = True) -> None:
        raise NotImplementedError("TODO: mark_validated")

    def add_quality_flag(self, model: str, version: int, description: str) -> int:
        """Open a data-quality flag and return its id."""
        raise NotImplementedError("TODO: add_quality_flag")

    def resolve_quality_flag(self, flag_id: int) -> None:
        """TODO: mark resolved; an unknown or already resolved flag -> ``RegistryError``."""
        raise NotImplementedError("TODO: resolve_quality_flag")

    def open_quality_flags(self, model: str, version: int) -> list[str]:
        """Descriptions of the still-open flags, oldest first."""
        raise NotImplementedError("TODO: open_quality_flags")

    # ------------------------------------------------------------- gates + transitions
    def check_promotion(self, model: str, version: int, policy: PromotionPolicy) -> GateResult:
        """Evaluate ALL gates and return every failure (do not stop at the first).

        TODO gates: (1) the run has ``policy.metric`` (final value) at all; (2) it meets ``policy.threshold``
        (``at_least``; flipped for lower-is-better); (3) if ANOTHER version is in Production, it beats that one by
        ``policy.min_improvement`` using ``meets_margin`` (skipped when nothing is in Production); (4) when
        ``policy.require_validated``, ``mark_validated`` was called; (5) no open data-quality flags.
        Reason texts should mention "threshold", "margin", "validated" and "open" respectively.
        """
        raise NotImplementedError("TODO: check_promotion")

    def transition(
        self,
        model: str,
        version: int,
        to_stage: Stage,
        *,
        policy: PromotionPolicy | None = None,
        reason: str = "",
    ) -> None:
        """Move a version to ``to_stage``.

        TODO: illegal move (see ALLOWED_TRANSITIONS, including "same stage") -> ``InvalidTransitionError``. Moving to
        Production needs a ``policy`` (``ValueError`` otherwise) and passing ``check_promotion`` (else
        ``PromotionBlockedError(reasons)``; nothing may change). A successful promotion archives the current
        Production version (reason "superseded by vN") in the SAME transaction (``with self._conn:``) so there is never
        more than one Production version. Every stage change appends a ``stage_history`` row.
        """
        raise NotImplementedError("TODO: transition")

    def rollback(self, model: str, *, reason: str = "") -> int:
        """Archive the current Production version and restore the version it superseded; return the restored number.

        TODO: no Production -> ``RollbackError``. Find the most recent version that entered Production BEFORE the
        current one did (use ``history``); none -> ``RollbackError``. Gates are NOT re-checked (emergency action);
        write history rows for both moves and include ``reason`` in their text.
        """
        raise NotImplementedError("TODO: rollback")
