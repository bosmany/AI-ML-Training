"""Per-namespace request/limit accounting."""
from __future__ import annotations

from collections.abc import Iterable

from .models import NamespaceTotals, PodInfo


def namespace_totals(pods: Iterable[PodInfo]) -> dict[str, NamespaceTotals]:
    """Sum requests/limits per namespace, keys sorted alphabetically.

    Pods in phase Succeeded or Failed (completed jobs, evicted pods) hold no resources: skip them.
    """
    raise NotImplementedError
