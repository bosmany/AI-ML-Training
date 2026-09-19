"""Turn ``kubectl get pods -o json`` into ``PodInfo`` objects and diagnose what is wrong with them."""
from __future__ import annotations

from typing import Any

from .models import (CRASH_LOOP, EVICTED, IMAGE_PULL, INIT_FAILED, OOM_KILLED, PENDING_UNSCHEDULABLE,
                     PodInfo, Problem, Resources)
from .quantity import cpu_to_millicores, memory_to_bytes

_IMAGE_REASONS = {"ImagePullBackOff", "ErrImagePull", "InvalidImageName", "ErrImageNeverPull"}


def _container_amounts(container: dict) -> tuple[int, int, int, int]:
    res = container.get("resources") or {}
    req, lim = res.get("requests") or {}, res.get("limits") or {}
    # Kubernetes defaults a missing request to the limit.
    cpu_lim = cpu_to_millicores(lim["cpu"]) if "cpu" in lim else 0
    mem_lim = memory_to_bytes(lim["memory"]) if "memory" in lim else 0
    cpu_req = cpu_to_millicores(req["cpu"]) if "cpu" in req else cpu_lim
    mem_req = memory_to_bytes(req["memory"]) if "memory" in req else mem_lim
    return cpu_req, cpu_lim, mem_req, mem_lim


def qos_class(spec: dict) -> str:
    """Guaranteed / Burstable / BestEffort computed from ``pod.spec`` (init containers count too).

    Guaranteed: every container has cpu AND memory limits and requests equal to them (or unset).
    BestEffort: no container sets any cpu/memory request or limit.  Everything else: Burstable.
    """
    containers = list(spec.get("initContainers") or []) + list(spec.get("containers") or [])
    any_set = False
    all_guaranteed = bool(containers)
    for c in containers:
        res = c.get("resources") or {}
        req, lim = res.get("requests") or {}, res.get("limits") or {}
        if any(k in d for d in (req, lim) for k in ("cpu", "memory")):
            any_set = True
        for resource in ("cpu", "memory"):
            if resource not in lim or (resource in req and _same(resource, req[resource], lim[resource]) is False):
                all_guaranteed = False
    if not any_set:
        return "BestEffort"
    return "Guaranteed" if all_guaranteed else "Burstable"


def _same(resource: str, a: str, b: str) -> bool:
    conv = cpu_to_millicores if resource == "cpu" else memory_to_bytes
    return conv(a) == conv(b)


def pod_resources(spec: dict) -> Resources:
    """Effective pod totals: max(sum(containers), max(init containers)) per resource, like the scheduler."""
    containers = spec.get("containers") or []
    inits = spec.get("initContainers") or []
    amounts = [_container_amounts(c) for c in containers]
    init_amounts = [_container_amounts(c) for c in inits]
    totals = []
    for i in range(4):
        total = sum(a[i] for a in amounts)
        biggest_init = max((a[i] for a in init_amounts), default=0)
        totals.append(max(total, biggest_init))
    without_limits = sum(1 for a in amounts if a[1] == 0 or a[3] == 0)
    return Resources(*totals, containers_without_limits=without_limits)


def diagnose_pod(pod: dict[str, Any]) -> list[Problem]:
    """Every problem visible in ``pod.status`` (a pod can have several, e.g. CrashLoopBackOff + OOMKilled)."""
    status = pod.get("status") or {}
    problems: list[Problem] = []

    if status.get("reason") == "Evicted":
        problems.append(Problem(EVICTED, status.get("message", "pod was evicted")))

    for cond in status.get("conditions") or []:
        if (cond.get("type") == "PodScheduled" and cond.get("status") == "False"
                and cond.get("reason") == "Unschedulable"):
            problems.append(Problem(PENDING_UNSCHEDULABLE, cond.get("message", "")))

    for cs in status.get("initContainerStatuses") or []:
        state = cs.get("state") or {}
        term = state.get("terminated")
        waiting = state.get("waiting") or {}
        last = (cs.get("lastState") or {}).get("terminated")
        if term and term.get("exitCode", 0) != 0:
            problems.append(Problem(INIT_FAILED, f"init container exited {term['exitCode']} ({term.get('reason', '')})", cs["name"]))
        elif waiting.get("reason") in ("CrashLoopBackOff", "Error") or (last and last.get("exitCode", 0) != 0):
            code = last.get("exitCode") if last else "?"
            problems.append(Problem(INIT_FAILED, f"init container failing (last exit code {code})", cs["name"]))

    for cs in status.get("containerStatuses") or []:
        name = cs["name"]
        waiting = (cs.get("state") or {}).get("waiting") or {}
        reason = waiting.get("reason")
        if reason == CRASH_LOOP:
            problems.append(Problem(CRASH_LOOP, f"restarted {cs.get('restartCount', 0)} times", name))
        elif reason in _IMAGE_REASONS:
            problems.append(Problem(IMAGE_PULL, waiting.get("message", reason), name))
        # OOM can be the CURRENT state or (usually) the last state of a restarted container
        for source in ((cs.get("state") or {}).get("terminated"), (cs.get("lastState") or {}).get("terminated")):
            if source and source.get("reason") == OOM_KILLED:
                problems.append(Problem(OOM_KILLED, f"container was OOMKilled (exit code {source.get('exitCode', 137)})", name))
                break
    return problems


def parse_pod_list(doc: dict[str, Any]) -> list[PodInfo]:
    """Parse a ``kind: List`` document (or a single Pod) into PodInfo, sorted by (namespace, name)."""
    items = doc["items"] if doc.get("kind") == "List" or "items" in doc else [doc]
    pods = []
    for item in items:
        meta, spec, status = item["metadata"], item.get("spec") or {}, item.get("status") or {}
        pods.append(PodInfo(
            namespace=meta.get("namespace", "default"),
            name=meta["name"],
            phase=status.get("phase", "Unknown"),
            node=spec.get("nodeName"),
            qos=qos_class(spec),
            resources=pod_resources(spec),
            problems=tuple(diagnose_pod(item)),
        ))
    return sorted(pods, key=lambda p: (p.namespace, p.name))
