"""Data classes shared by the tracker and the registry (scaffold - provided)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class RunStatus(str, Enum):
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"
    FAILED = "FAILED"


class Stage(str, Enum):
    NONE = "None"
    STAGING = "Staging"
    PRODUCTION = "Production"
    ARCHIVED = "Archived"


@dataclass(frozen=True)
class Run:
    run_id: str
    experiment: str
    name: str | None
    status: RunStatus
    start_time: datetime
    end_time: datetime | None
    dataset_hash: str | None
    code_version: str | None
    params: dict[str, str] = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)  # FINAL value per key (highest step)
    artifacts: dict[str, str] = field(default_factory=dict)  # artifact name -> sha256 hex


@dataclass(frozen=True)
class Comparison:
    # metrics[run_id][metric_key] -> final value, or None if that run never logged it
    metrics: dict[str, dict[str, float | None]]
    # only params whose value is NOT the same in every compared run: differing_params[key][run_id] -> value | None
    differing_params: dict[str, dict[str, str | None]]


@dataclass(frozen=True)
class ModelVersion:
    model: str
    version: int
    run_id: str
    stage: Stage
    validated: bool
    created_at: datetime


@dataclass(frozen=True)
class PromotionPolicy:
    """The gates a Staging version must pass to become Production."""

    metric: str
    threshold: float  # absolute bar: >= threshold (higher_is_better) or <= threshold (lower is better)
    min_improvement: float = 0.0  # must beat the CURRENT production version by at least this much
    higher_is_better: bool = True
    require_validated: bool = True


@dataclass(frozen=True)
class GateResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Lineage:
    model: str
    version: int
    run_id: str
    dataset_hash: str
    code_version: str
    params: dict[str, str]
    artifacts: dict[str, str]


@dataclass(frozen=True)
class HistoryEvent:
    seq: int
    model: str
    version: int
    from_stage: Stage
    to_stage: Stage
    reason: str
    at: datetime
