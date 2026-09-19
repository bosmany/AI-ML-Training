"""Per-namespace request/limit accounting."""
from __future__ import annotations

from collections.abc import Iterable

from .models import NamespaceTotals, PodInfo

_DONE_PHASES = {"Succeeded", "Failed"}  # they no longer hold resources on a node


def namespace_totals(pods: Iterable[PodInfo]) -> dict[str, NamespaceTotals]:
    totals: dict[str, NamespaceTotals] = {}
    for pod in pods:
        if pod.phase in _DONE_PHASES:
            continue
        t = totals.setdefault(pod.namespace, NamespaceTotals())
        t.pods += 1
        t.cpu_request_m += pod.resources.cpu_request_m
        t.cpu_limit_m += pod.resources.cpu_limit_m
        t.mem_request += pod.resources.mem_request
        t.mem_limit += pod.resources.mem_limit
        t.containers_without_limits += pod.resources.containers_without_limits
    return dict(sorted(totals.items()))
