"""The six rules to implement (starter). Metadata (id, severity, description) is provided; you write ``check``.

Use ``iter_containers(doc.data)`` to get every compose service / Kubernetes container as a ``ContainerRef``
(``c.kind`` is "compose" or "k8s", ``c.spec`` the mapping, ``c.pointer`` its JSON pointer). Build findings with
``self.finding(doc, pointer, message)`` - it fills in file, severity and the line number. ``pointer_join(c.pointer, "image")``
makes the pointer of a key inside the container. Real files are messy: never assume a value has the type you expect.
"""

from __future__ import annotations

import re
from typing import Any  # noqa: F401

from lab.loader import pointer_join  # noqa: F401
from lab.models import Document, Finding, Severity
from lab.rule import Rule
from lab.walk import ContainerRef, iter_containers  # noqa: F401

SECRET_NAME_RE = re.compile(r"(PASSWORD|PASSWD|SECRET(_KEY)?|TOKEN|API_?KEY|PRIVATE_KEY|ACCESS_KEY)$", re.IGNORECASE)
INTERPOLATION_RE = re.compile(r"^\$\{?[A-Za-z_]")  # ${VAR} or $VAR: value comes from the environment, not the file
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


class NoLatestTag(Rule):
    id = "no-latest-tag"
    severity = Severity.MEDIUM
    description = "Images must be pinned to a version tag or digest, not ':latest' or untagged."

    def check(self, doc: Document) -> list[Finding]:
        """Flag ``image`` (pointer ``<container>/image``) when it has tag ``latest`` (any case) or no tag at all.

        TODO. Look-alikes that must NOT be flagged: ``registry.local:5000/app:1.2`` (the first ':' is a registry
        port - only look for a tag in the LAST path segment), ``nginx@sha256:...`` (digest pin), images containing
        ``${...}`` interpolation, non-string / missing images (build-only compose services), ``latest-tools:1.0``.
        But ``registry.local:5000/app`` (no tag) IS flagged.
        """
        raise NotImplementedError("TODO: implement NoLatestTag.check")


class ResourceLimits(Rule):
    id = "resource-limits"
    severity = Severity.MEDIUM
    description = "Containers need memory (and, on Kubernetes, CPU) limits."

    def check(self, doc: Document) -> list[Finding]:
        """Compose: need ``mem_limit`` or ``deploy.resources.limits.memory``; finding pointer = the service.
        (``deploy.resources.reservations`` are NOT limits.)

        Kubernetes: ``resources.limits`` must have BOTH ``cpu`` and ``memory``. No limits at all -> pointer = the
        container; some limits but incomplete -> pointer = ``<container>/resources/limits`` and the message names
        only the missing resource(s). TODO.
        """
        raise NotImplementedError("TODO: implement ResourceLimits.check")


class MissingProbes(Rule):
    id = "missing-probes"
    severity = Severity.LOW
    description = "Long-running workloads need liveness/readiness probes (compose: a healthcheck)."

    def check(self, doc: Document) -> list[Finding]:
        """Compose: no ``healthcheck`` (or ``healthcheck.disable: true``) -> one finding at the service.

        Kubernetes: one finding per container, pointer = the container, message naming the missing probe(s)
        (``livenessProbe`` and/or ``readinessProbe``). ``Job`` and ``CronJob`` workloads (``c.workload``) run to
        completion and are exempt. TODO.
        """
        raise NotImplementedError("TODO: implement MissingProbes.check")


class NoPrivileged(Rule):
    id = "no-privileged"
    severity = Severity.CRITICAL
    description = "Containers must not run in privileged mode."

    def check(self, doc: Document) -> list[Finding]:
        """Compose: ``privileged: true`` on the service (pointer ``<service>/privileged``).
        Kubernetes: ``securityContext.privileged: true`` on the container (pointer ``.../securityContext/privileged``).
        ``false`` or absent is fine. TODO.
        """
        raise NotImplementedError("TODO: implement NoPrivileged.check")


class NoPlaintextSecrets(Rule):
    id = "no-plaintext-secrets"
    severity = Severity.HIGH
    description = "Secrets must come from a secret store or the environment, never literal values in the file."

    def check(self, doc: Document) -> list[Finding]:
        """Look at environment variables whose NAME matches ``SECRET_NAME_RE`` and whose value is a literal.

        Compose ``environment`` is a mapping (pointer ``.../environment/NAME``) OR a list of ``"NAME=value"``
        strings (pointer ``.../environment/<index>``). Kubernetes ``env`` is a list of ``{name, value}`` (pointer
        ``.../env/<i>/value``); ``valueFrom`` entries have no ``value`` and are fine.

        NOT findings: ``${VAR}`` / ``$VAR`` values (``INTERPOLATION_RE``), names ending in ``_FILE``, empty or
        missing values (passthrough like ``- DB_PASSWORD``), booleans (``TOKEN_ENABLED: true``), names that merely
        contain a keyword (``SECRET_PATH``). TODO.
        """
        raise NotImplementedError("TODO: implement NoPlaintextSecrets.check")


class NoExposedPorts(Rule):
    id = "no-exposed-ports"
    severity = Severity.MEDIUM
    description = "Publish ports on loopback only; hostPort and 0.0.0.0 bindings expose the container."

    def check(self, doc: Document) -> list[Finding]:
        """Compose ``ports`` (pointer ``<service>/ports/<i>``): exposed unless bound to a loopback address.
        Short syntax: ``"8080:80"``, ``"80"``, ``"0.0.0.0:8080:80"``, ``"8080:80/udp"`` and plain ints are exposed;
        ``"127.0.0.1:8080:80"``, ``"[::1]:8080:80"``, ``"localhost:..."`` are not (``LOOPBACK_HOSTS``). Long syntax:
        a mapping with ``host_ip`` (missing -> exposed). ``expose:`` is not a finding.

        Kubernetes: a container port with a ``hostPort``. Plain ``containerPort`` is fine. TODO.
        """
        raise NotImplementedError("TODO: implement NoExposedPorts.check")


DEFAULT_RULES: tuple[Rule, ...] = (
    NoLatestTag(),
    ResourceLimits(),
    MissingProbes(),
    NoPrivileged(),
    NoPlaintextSecrets(),
    NoExposedPorts(),
)
