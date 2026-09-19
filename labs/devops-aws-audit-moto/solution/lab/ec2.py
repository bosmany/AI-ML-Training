"""EC2 checks: untagged instances, instances stopped for too long, security groups open to the world."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from .client import list_all
from .models import AuditConfig, AuditResult, Finding

# "User initiated (2024-01-01 12:00:00 GMT)"  (moto writes UTC, real AWS writes GMT)
_STOPPED_RE = re.compile(r"\((\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?:GMT|UTC)\)")


def _instances(ec2, cfg: AuditConfig) -> list[dict]:
    reservations = list_all(ec2, "describe_instances", "Reservations",
                            page_size=cfg.page_size, max_attempts=cfg.max_attempts, sleep=cfg.sleep)
    return [i for r in reservations for i in r.get("Instances", [])]


def stopped_at(instance: dict) -> datetime | None:
    """When the instance entered ``stopped``, parsed from StateTransitionReason; None if unknown."""
    m = _STOPPED_RE.search(instance.get("StateTransitionReason", ""))
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def audit_ec2(ec2, cfg: AuditConfig) -> AuditResult:
    result = AuditResult()
    for inst in _instances(ec2, cfg):
        state = inst["State"]["Name"]
        if state in ("terminated", "shutting-down"):
            continue
        iid = inst["InstanceId"]
        tags = {t["Key"]: t.get("Value", "") for t in inst.get("Tags", [])}
        missing = [k for k in cfg.required_tags if not tags.get(k)]
        if missing:
            result.findings.append(Finding(
                "ec2-untagged", iid, "medium",
                f"Instance {iid} is missing required tag(s): {', '.join(missing)}",
                {"missing_tags": missing, "state": state},
            ))
        if state == "stopped":
            since = stopped_at(inst)
            if since is not None and cfg.now - since > timedelta(days=cfg.stopped_max_days):
                days = (cfg.now - since).days
                result.findings.append(Finding(
                    "ec2-stopped-too-long", iid, "low",
                    f"Instance {iid} has been stopped for {days} days (limit {cfg.stopped_max_days})",
                    {"stopped_days": days, "stopped_at": since.isoformat()},
                ))
    return result


_PROTOCOLS = {"tcp": "tcp", "6": "tcp", "udp": "udp", "17": "udp"}


def exposed_ports(permission: dict, sensitive: frozenset[int]) -> list[int] | str:
    """Sensitive ports reachable through one ingress permission; ``"all"`` for protocol -1; [] if none."""
    proto = str(permission.get("IpProtocol"))
    if proto == "-1":
        return "all"
    if proto not in _PROTOCOLS:
        return []
    lo = permission.get("FromPort", 0)
    hi = permission.get("ToPort", 65535)
    return sorted(p for p in sensitive if lo <= p <= hi)


def audit_security_groups(ec2, cfg: AuditConfig) -> AuditResult:
    result = AuditResult()
    groups = list_all(ec2, "describe_security_groups", "SecurityGroups",
                      page_size=cfg.page_size, max_attempts=cfg.max_attempts, sleep=cfg.sleep)
    for sg in groups:
        for perm in sg.get("IpPermissions", []):
            ports = exposed_ports(perm, cfg.sensitive_ports)
            if not ports:
                continue
            cidrs = [r["CidrIp"] for r in perm.get("IpRanges", []) if r.get("CidrIp") == "0.0.0.0/0"]
            cidrs += [r["CidrIpv6"] for r in perm.get("Ipv6Ranges", []) if r.get("CidrIpv6") == "::/0"]
            for cidr in cidrs:
                what = "ALL traffic" if ports == "all" else f"port(s) {', '.join(map(str, ports))}"
                result.findings.append(Finding(
                    "sg-open-ingress", sg["GroupId"], "high",
                    f"Security group {sg['GroupId']} ({sg.get('GroupName', '')}) allows {cidr} to {what}",
                    {"cidr": cidr, "protocol": str(perm.get("IpProtocol")), "ports": ports,
                     "from_port": perm.get("FromPort"), "to_port": perm.get("ToPort")},
                ))
    return result
