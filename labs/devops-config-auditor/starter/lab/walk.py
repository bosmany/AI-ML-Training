"""Find the "containers" inside docker-compose and Kubernetes documents. PROVIDED.

Rules look at one container at a time; this module hides where each format keeps them.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from lab.loader import pointer_join

POD_TEMPLATE_KINDS = {"Deployment", "StatefulSet", "DaemonSet", "ReplicaSet", "Job", "ReplicationController"}


@dataclass(frozen=True)
class ContainerRef:
    kind: str  # "compose" or "k8s"
    workload: str  # compose: "service"; k8s: the object kind ("Deployment", "Job", ...)
    name: str
    pointer: str  # JSON pointer of the container / service mapping
    spec: dict[str, Any]


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _k8s_containers(pod_spec: Any, base: str, workload: str) -> Iterator[ContainerRef]:
    containers = _dict(pod_spec).get("containers")
    if not isinstance(containers, list):
        return
    for i, spec in enumerate(containers):
        if isinstance(spec, dict):
            yield ContainerRef("k8s", workload, str(spec.get("name", i)), pointer_join(base, "containers", i), spec)


def iter_containers(data: Any) -> Iterator[ContainerRef]:
    """Yield every compose service / Kubernetes container of a parsed document. Odd shapes yield nothing."""
    doc = _dict(data)
    if "kind" in doc:
        kind = str(doc["kind"])
        spec = _dict(doc.get("spec"))
        if kind == "Pod":
            yield from _k8s_containers(spec, "/spec", kind)
        elif kind in POD_TEMPLATE_KINDS:
            yield from _k8s_containers(_dict(spec.get("template")).get("spec"), "/spec/template/spec", kind)
        elif kind == "CronJob":
            template = _dict(_dict(spec.get("jobTemplate")).get("spec")).get("template")
            yield from _k8s_containers(_dict(template).get("spec"), "/spec/jobTemplate/spec/template/spec", kind)
    elif isinstance(doc.get("services"), dict):
        for name, service in doc["services"].items():
            if isinstance(service, dict):
                yield ContainerRef("compose", "service", str(name), pointer_join("/services", name), service)
