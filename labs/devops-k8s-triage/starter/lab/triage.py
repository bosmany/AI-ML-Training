"""Glue: fetch pods+nodes, diagnose, aggregate, render."""
from __future__ import annotations

from typing import Any

from .kubectl import Kubectl
from .models import TriageReport


def build_report(pods_doc: dict[str, Any], nodes_doc: dict[str, Any]) -> TriageReport:
    """TriageReport(pods_with_problems=[pods that have problems], nodes_with_problems=[...],
    namespaces=namespace_totals(ALL pods))."""
    raise NotImplementedError


def triage_cluster(kubectl: Kubectl) -> TriageReport:
    """Fetch all pods and nodes through the wrapper and build the report."""
    raise NotImplementedError


def render_report(report: TriageReport) -> str:
    """Plain text with three sections: "NODES WITH PROBLEMS", "PODS WITH PROBLEMS" (namespace/name, phase,
    QoS, sorted unique kinds) and "NAMESPACE TOTALS" (e.g. "prod: 3 pods, cpu req 700m / lim 800m, mem req
    448Mi / lim 576Mi, N container(s) without limits"). An empty section prints "  none"."""
    raise NotImplementedError
