"""Data structures shared by every check."""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass(frozen=True)
class AuditConfig:
    """Everything a check needs that is not an AWS client. ``now`` and ``sleep`` are injected for tests."""

    now: datetime  # timezone-aware
    required_tags: tuple[str, ...] = ("Owner",)
    stopped_max_days: int = 30
    key_max_age_days: int = 90
    sensitive_ports: frozenset[int] = frozenset({22, 3389, 3306, 5432, 6379, 27017})
    page_size: int | None = None  # None -> let AWS choose
    max_attempts: int = 5
    sleep: Callable[[float], None] = time.sleep

    def __post_init__(self) -> None:
        if self.now.tzinfo is None:
            raise ValueError("AuditConfig.now must be timezone-aware (naive datetimes cause silent off-by-hours bugs)")


@dataclass(frozen=True)
class Finding:
    check: str  # e.g. "ec2-untagged"
    resource: str  # instance id, sg id, bucket name, user name ...
    severity: str  # "high" | "medium" | "low"
    message: str
    details: dict = field(default_factory=dict)


@dataclass(frozen=True)
class AuditError:
    """A check that could not run (or could not finish for one resource). Never swallowed silently."""

    check: str
    resource: str | None
    code: str  # AWS error code, e.g. "AccessDenied"
    message: str


@dataclass
class AuditResult:
    findings: list[Finding] = field(default_factory=list)
    errors: list[AuditError] = field(default_factory=list)

    def extend(self, other: AuditResult) -> None:
        self.findings.extend(other.findings)
        self.errors.extend(other.errors)


@dataclass
class AuditReport:
    generated_at: datetime
    findings: list[Finding]
    errors: list[AuditError]
