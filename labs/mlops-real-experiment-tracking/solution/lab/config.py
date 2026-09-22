"""Dataclasses shared by train.py, registry.py and query.py. Provided - do not edit."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RunConfig:
    """One training configuration. ``random_state`` is fixed so re-running is reproducible."""

    n_estimators: int
    max_depth: int | None = None
    random_state: int = 42


@dataclass(frozen=True)
class TrainedRun:
    """What a finished, logged MLflow run looks like to the rest of the lab."""

    run_id: str
    accuracy: float
    f1: float
    error_rate: float
    model_uri: str


@dataclass(frozen=True)
class PromotedVersion:
    """A model version after it has been registered and moved through the stage machine."""

    name: str
    version: str
    run_id: str
    stage: str


@dataclass(frozen=True)
class RunSummary:
    """A run as read back from the tracking server: real params/metrics, not what we logged from memory."""

    run_id: str
    params: dict[str, str] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    start_time: int = 0
