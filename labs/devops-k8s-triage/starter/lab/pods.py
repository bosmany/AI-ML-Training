"""Turn ``kubectl get pods -o json`` into ``PodInfo`` objects and diagnose what is wrong with them."""
from __future__ import annotations

from typing import Any

from .models import (CRASH_LOOP, EVICTED, IMAGE_PULL, INIT_FAILED, OOM_KILLED, PENDING_UNSCHEDULABLE,  # noqa: F401
                     PodInfo, Problem, Resources)
from .quantity import cpu_to_millicores, memory_to_bytes  # noqa: F401


def qos_class(spec: dict) -> str:
    """"Guaranteed" / "Burstable" / "BestEffort" computed from ``pod.spec`` (NOT status.qosClass).

    - Guaranteed: EVERY container (init containers included) has cpu AND memory limits, and any request
      that is set equals its limit (compare parsed VALUES: "1" == "1000m"). A missing request defaults to the limit.
    - BestEffort: no container sets any cpu/memory request or limit.
    - Burstable: everything else.
    """
    raise NotImplementedError


def pod_resources(spec: dict) -> Resources:
    """Effective totals for the pod (cpu in millicores, memory in bytes).

    - a missing request defaults to that container's limit
    - per resource: max(sum over containers, largest single init container) - init containers run one at a time
    - ``containers_without_limits``: app containers missing a cpu OR a memory limit
    """
    raise NotImplementedError


def diagnose_pod(pod: dict[str, Any]) -> list[Problem]:
    """Every problem visible in ``pod['status']`` (one pod may have several). Kinds are constants from models:

    - CRASH_LOOP: a containerStatus waiting with reason CrashLoopBackOff (detail mentions restartCount)
    - IMAGE_PULL: waiting reason ImagePullBackOff / ErrImagePull (and similar)
    - OOM_KILLED: terminated.reason == "OOMKilled" in EITHER state or lastState (a restarted container looks
      healthy in ``state``!)
    - PENDING_UNSCHEDULABLE: condition PodScheduled=False with reason Unschedulable (detail = scheduler message)
    - EVICTED: status.reason == "Evicted" (detail = status.message)
    - INIT_FAILED: an initContainerStatus that terminated non-zero, or is waiting in CrashLoopBackOff / has a
      non-zero lastState exit code (set Problem.container to the init container name)
    Tolerate a pod without ``status``.
    """
    raise NotImplementedError


def parse_pod_list(doc: dict[str, Any]) -> list[PodInfo]:
    """Parse a ``kind: List`` document (or one Pod) into PodInfo, sorted by (namespace, name).

    namespace defaults to "default", phase to "Unknown"; node = spec.nodeName (None while Pending unscheduled).
    """
    raise NotImplementedError
