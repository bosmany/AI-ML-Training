"""Node parsing and health diagnosis."""
from __future__ import annotations

from typing import Any

from .models import NODE_NOT_READY, NodeInfo, Problem  # noqa: F401

PRESSURE_CONDITIONS = ("MemoryPressure", "DiskPressure", "PIDPressure")


def parse_node_list(doc: dict[str, Any]) -> list[NodeInfo]:
    """Parse ``kubectl get nodes -o json`` into NodeInfo sorted by name.

    - ready: condition Ready has status "True". "False" AND "Unknown" (kubelet stopped posting) are NOT ready
      -> Problem(NODE_NOT_READY, ...)
    - pressures: only conditions whose status is exactly "True" (Unknown is not pressure); each also becomes
      a Problem(<condition type>, message)
    - unschedulable = spec.unschedulable (cordoned) - reported as a flag, NOT as a problem
    - allocatable cpu/memory parsed with the quantity helpers (0 when absent)
    """
    raise NotImplementedError
