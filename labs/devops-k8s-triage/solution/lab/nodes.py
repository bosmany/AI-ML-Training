"""Node parsing and health diagnosis."""
from __future__ import annotations

from typing import Any

from .models import NODE_NOT_READY, NodeInfo, Problem
from .quantity import cpu_to_millicores, memory_to_bytes

PRESSURE_CONDITIONS = ("MemoryPressure", "DiskPressure", "PIDPressure")


def parse_node_list(doc: dict[str, Any]) -> list[NodeInfo]:
    items = doc["items"] if "items" in doc else [doc]
    nodes = []
    for item in items:
        status = item.get("status") or {}
        conds = {c["type"]: c for c in status.get("conditions") or []}
        ready_cond = conds.get("Ready", {})
        ready = ready_cond.get("status") == "True"
        pressures = tuple(t for t in PRESSURE_CONDITIONS if conds.get(t, {}).get("status") == "True")
        problems: list[Problem] = []
        if not ready:
            why = "kubelet stopped posting status" if ready_cond.get("status") == "Unknown" else ready_cond.get("message", "not ready")
            problems.append(Problem(NODE_NOT_READY, why))
        problems += [Problem(p, conds[p].get("message", "")) for p in pressures]
        alloc = status.get("allocatable") or {}
        nodes.append(NodeInfo(
            name=item["metadata"]["name"],
            ready=ready,
            unschedulable=bool((item.get("spec") or {}).get("unschedulable")),
            pressures=pressures,
            allocatable_cpu_m=cpu_to_millicores(alloc["cpu"]) if "cpu" in alloc else 0,
            allocatable_mem=memory_to_bytes(alloc["memory"]) if "memory" in alloc else 0,
            problems=tuple(problems),
        ))
    return sorted(nodes, key=lambda n: n.name)
