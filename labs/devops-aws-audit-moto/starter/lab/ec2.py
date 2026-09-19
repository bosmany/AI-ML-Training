"""EC2 checks: untagged instances, instances stopped for too long, security groups open to the world."""
from __future__ import annotations

import re
from datetime import datetime

from .client import list_all
from .models import AuditConfig, AuditResult, Finding

# "User initiated (2024-01-01 12:00:00 GMT)"  (moto writes UTC, real AWS writes GMT)
_STOPPED_RE = re.compile(r"\((\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?:GMT|UTC)\)")


def stopped_at(instance: dict) -> datetime | None:
    """When the instance entered ``stopped`` (UTC, timezone-aware), parsed from ``StateTransitionReason``.

    Returns None when the reason has no timestamp (e.g. an instance that was never stopped).
    """
    raise NotImplementedError


def audit_ec2(ec2, cfg: AuditConfig) -> AuditResult:
    """Two checks over all instances (use ``list_all`` for "describe_instances"/"Reservations";
    instances are nested inside reservations; pass cfg.page_size, cfg.max_attempts, cfg.sleep).

    - "ec2-untagged" (severity "medium"): a tag in ``cfg.required_tags`` is missing OR has an empty value.
      details={"missing_tags": [...], "state": ...}
    - "ec2-stopped-too-long" (severity "low"): state is ``stopped`` and ``cfg.now - stopped_at`` is STRICTLY
      greater than ``cfg.stopped_max_days`` days. details={"stopped_days": int, "stopped_at": iso}
    Skip terminated/shutting-down instances entirely.
    """
    raise NotImplementedError


def exposed_ports(permission: dict, sensitive: frozenset[int]) -> list[int] | str:
    """Sensitive ports reachable through ONE ``IpPermissions`` entry.

    - protocol "-1" (all traffic) has no FromPort/ToPort in the API response -> return the string "all"
    - tcp / "6" and udp / "17": sorted sensitive ports with FromPort <= port <= ToPort (inclusive)
    - anything else (icmp ...) -> []
    """
    raise NotImplementedError


def audit_security_groups(ec2, cfg: AuditConfig) -> AuditResult:
    """"sg-open-ingress" (severity "high"): one Finding per (rule, world CIDR) where the CIDR is
    0.0.0.0/0 (IpRanges) or ::/0 (Ipv6Ranges) and ``exposed_ports`` is non-empty.
    resource = GroupId; details={"cidr", "protocol", "ports", "from_port", "to_port"}.
    Only look at ingress (``IpPermissions``)."""
    raise NotImplementedError
