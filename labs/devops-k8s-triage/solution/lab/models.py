"""Plain data containers."""
from __future__ import annotations

from dataclasses import dataclass, field

# Problem kinds reported by the diagnosers
CRASH_LOOP = "CrashLoopBackOff"
IMAGE_PULL = "ImagePullBackOff"
OOM_KILLED = "OOMKilled"
PENDING_UNSCHEDULABLE = "PendingUnschedulable"
EVICTED = "Evicted"
INIT_FAILED = "InitContainerFailed"

NODE_NOT_READY = "NotReady"


@dataclass(frozen=True)
class Problem:
    kind: str
    detail: str
    container: str | None = None


@dataclass(frozen=True)
class Resources:
    """Effective totals for one pod. cpu in millicores, memory in bytes. 0 = not set."""

    cpu_request_m: int = 0
    cpu_limit_m: int = 0
    mem_request: int = 0
    mem_limit: int = 0
    containers_without_limits: int = 0


@dataclass(frozen=True)
class PodInfo:
    namespace: str
    name: str
    phase: str
    node: str | None
    qos: str
    resources: Resources
    problems: tuple[Problem, ...] = ()


@dataclass(frozen=True)
class NodeInfo:
    name: str
    ready: bool
    unschedulable: bool
    pressures: tuple[str, ...]  # e.g. ("DiskPressure",)
    allocatable_cpu_m: int
    allocatable_mem: int
    problems: tuple[Problem, ...] = ()


@dataclass
class NamespaceTotals:
    pods: int = 0
    cpu_request_m: int = 0
    cpu_limit_m: int = 0
    mem_request: int = 0
    mem_limit: int = 0
    containers_without_limits: int = 0


@dataclass
class TriageReport:
    pods_with_problems: list[PodInfo] = field(default_factory=list)
    nodes_with_problems: list[NodeInfo] = field(default_factory=list)
    namespaces: dict[str, NamespaceTotals] = field(default_factory=dict)
