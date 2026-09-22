"""The six shipped rules (reference solution)."""

from __future__ import annotations

import re
from typing import Any

from lab.loader import pointer_join
from lab.models import Document, Finding, Severity
from lab.rule import Rule
from lab.walk import ContainerRef, iter_containers

SECRET_NAME_RE = re.compile(r"(PASSWORD|PASSWD|SECRET(_KEY)?|TOKEN|API_?KEY|PRIVATE_KEY|ACCESS_KEY)$", re.IGNORECASE)
INTERPOLATION_RE = re.compile(r"^\$\{?[A-Za-z_]")
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


class NoLatestTag(Rule):
    id = "no-latest-tag"
    severity = Severity.MEDIUM
    description = "Images must be pinned to a version tag or digest, not ':latest' or untagged."

    def check(self, doc: Document) -> list[Finding]:
        out = []
        for c in iter_containers(doc.data):
            image = c.spec.get("image")
            if not isinstance(image, str) or "@" in image or "${" in image:
                continue
            last_segment = image.rsplit("/", 1)[-1]  # a ':' before the last '/' is a registry port, not a tag
            tag = last_segment.split(":", 1)[1] if ":" in last_segment else None
            if tag is None or tag.lower() == "latest":
                shown = f"tag ':{tag}'" if tag else "no tag (implicitly ':latest')"
                out.append(self.finding(doc, pointer_join(c.pointer, "image"), f"image '{image}' uses {shown}"))
        return out


class ResourceLimits(Rule):
    id = "resource-limits"
    severity = Severity.MEDIUM
    description = "Containers need memory (and, on Kubernetes, CPU) limits."

    def check(self, doc: Document) -> list[Finding]:
        out = []
        for c in iter_containers(doc.data):
            if c.kind == "compose":
                limits = _dict(_dict(_dict(c.spec.get("deploy")).get("resources")).get("limits"))
                if not (c.spec.get("mem_limit") or limits.get("memory")):
                    out.append(self.finding(doc, c.pointer, f"service '{c.name}' has no memory limit"))
            else:
                limits = _dict(_dict(c.spec.get("resources")).get("limits"))
                missing = [k for k in ("cpu", "memory") if not limits.get(k)]
                if missing:
                    where = pointer_join(c.pointer, "resources", "limits") if limits else c.pointer
                    out.append(self.finding(doc, where, f"container '{c.name}' has no {' and '.join(missing)} limit"))
        return out


class MissingProbes(Rule):
    id = "missing-probes"
    severity = Severity.LOW
    description = "Long-running workloads need liveness/readiness probes (compose: a healthcheck)."

    def check(self, doc: Document) -> list[Finding]:
        out = []
        for c in iter_containers(doc.data):
            if c.kind == "compose":
                hc = c.spec.get("healthcheck")
                if not hc or (isinstance(hc, dict) and hc.get("disable") is True):
                    out.append(self.finding(doc, c.pointer, f"service '{c.name}' has no healthcheck"))
            elif c.workload not in ("Job", "CronJob"):  # run-to-completion workloads do not need probes
                missing = [p for p in ("livenessProbe", "readinessProbe") if not c.spec.get(p)]
                if missing:
                    out.append(self.finding(doc, c.pointer, f"container '{c.name}' has no {' or '.join(missing)}"))
        return out


class NoPrivileged(Rule):
    id = "no-privileged"
    severity = Severity.CRITICAL
    description = "Containers must not run in privileged mode."

    def check(self, doc: Document) -> list[Finding]:
        out = []
        for c in iter_containers(doc.data):
            if c.kind == "compose":
                flag, pointer = c.spec.get("privileged"), pointer_join(c.pointer, "privileged")
            else:
                flag = _dict(c.spec.get("securityContext")).get("privileged")
                pointer = pointer_join(c.pointer, "securityContext", "privileged")
            if flag is True or (isinstance(flag, str) and flag.strip().lower() == "true"):
                out.append(self.finding(doc, pointer, f"'{c.name}' runs privileged"))
        return out


class NoPlaintextSecrets(Rule):
    id = "no-plaintext-secrets"
    severity = Severity.HIGH
    description = "Secrets must come from a secret store or the environment, never literal values in the file."

    @staticmethod
    def _is_literal_secret(name: str, value: Any) -> bool:
        if not SECRET_NAME_RE.search(name):  # anchored at the end, so FOO_PASSWORD_FILE never matches
            return False
        if isinstance(value, bool) or value is None:
            return False
        text = str(value).strip()
        return bool(text) and not INTERPOLATION_RE.match(text)

    def _entries(self, c: ContainerRef) -> list[tuple[str, Any, str]]:
        """(name, value, pointer) for every env var of the container."""
        out: list[tuple[str, Any, str]] = []
        if c.kind == "compose":
            env = c.spec.get("environment")
            if isinstance(env, dict):
                out = [(str(k), v, pointer_join(c.pointer, "environment", k)) for k, v in env.items()]
            elif isinstance(env, list):
                for i, item in enumerate(env):
                    if isinstance(item, str) and "=" in item:
                        name, value = item.split("=", 1)
                        out.append((name, value, pointer_join(c.pointer, "environment", i)))
        else:
            env = c.spec.get("env")
            if isinstance(env, list):
                for i, item in enumerate(env):
                    if isinstance(item, dict) and "name" in item and "value" in item:  # valueFrom has no 'value'
                        out.append((str(item["name"]), item["value"], pointer_join(c.pointer, "env", i, "value")))
        return out

    def check(self, doc: Document) -> list[Finding]:
        out = []
        for c in iter_containers(doc.data):
            for name, value, pointer in self._entries(c):
                if self._is_literal_secret(name, value):
                    out.append(self.finding(doc, pointer, f"'{name}' in '{c.name}' is a plaintext secret"))
        return out


class NoExposedPorts(Rule):
    id = "no-exposed-ports"
    severity = Severity.MEDIUM
    description = "Publish ports on loopback only; hostPort and 0.0.0.0 bindings expose the container."

    @staticmethod
    def _compose_exposed(port: Any) -> bool:
        if isinstance(port, dict):
            return str(port.get("host_ip", "")).lower() not in LOOPBACK_HOSTS
        if isinstance(port, bool) or not isinstance(port, (str, int)):
            return False
        text = str(port).split("/", 1)[0]
        if text.startswith("["):  # [::1]:8080:80
            host_ip = text[1 : text.index("]")] if "]" in text else ""
        else:
            parts = text.split(":")
            host_ip = parts[0] if len(parts) == 3 else ""
        return host_ip.lower() not in LOOPBACK_HOSTS

    def check(self, doc: Document) -> list[Finding]:
        out = []
        for c in iter_containers(doc.data):
            ports = c.spec.get("ports")
            if not isinstance(ports, list):
                continue
            for i, port in enumerate(ports):
                pointer = pointer_join(c.pointer, "ports", i)
                if c.kind == "compose" and self._compose_exposed(port):
                    out.append(self.finding(doc, pointer, f"port {port!r} of '{c.name}' is published on all interfaces"))
                elif c.kind == "k8s" and isinstance(port, dict) and port.get("hostPort"):
                    out.append(self.finding(doc, pointer, f"'{c.name}' binds hostPort {port['hostPort']} on the node"))
        return out


DEFAULT_RULES: tuple[Rule, ...] = (
    NoLatestTag(),
    ResourceLimits(),
    MissingProbes(),
    NoPrivileged(),
    NoPlaintextSecrets(),
    NoExposedPorts(),
)
