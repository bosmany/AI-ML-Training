"""Glue: fetch pods+nodes, diagnose, aggregate, render."""
from __future__ import annotations

from typing import Any

from .aggregate import namespace_totals
from .kubectl import Kubectl
from .models import TriageReport
from .nodes import parse_node_list
from .pods import parse_pod_list


def build_report(pods_doc: dict[str, Any], nodes_doc: dict[str, Any]) -> TriageReport:
    pods = parse_pod_list(pods_doc)
    nodes = parse_node_list(nodes_doc)
    return TriageReport(
        pods_with_problems=[p for p in pods if p.problems],
        nodes_with_problems=[n for n in nodes if n.problems],
        namespaces=namespace_totals(pods),
    )


def triage_cluster(kubectl: Kubectl) -> TriageReport:
    return build_report(kubectl.get_pods(), kubectl.get_nodes())


def render_report(report: TriageReport) -> str:
    lines = ["NODES WITH PROBLEMS"]
    lines += [f"  {n.name}: " + "; ".join(f"{p.kind} ({p.detail})" if p.detail else p.kind for p in n.problems)
              for n in report.nodes_with_problems] or ["  none"]
    lines += ["", "PODS WITH PROBLEMS"]
    lines += [f"  {p.namespace}/{p.name} [{p.phase}, {p.qos}]: " + ", ".join(sorted({x.kind for x in p.problems}))
              for p in report.pods_with_problems] or ["  none"]
    lines += ["", "NAMESPACE TOTALS (running/pending pods)"]
    for ns, t in report.namespaces.items():
        lines.append(f"  {ns}: {t.pods} pods, cpu req {t.cpu_request_m}m / lim {t.cpu_limit_m}m, "
                     f"mem req {t.mem_request // 2**20}Mi / lim {t.mem_limit // 2**20}Mi, "
                     f"{t.containers_without_limits} container(s) without limits")
    return "\n".join(lines)
