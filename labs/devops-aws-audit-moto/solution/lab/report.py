"""Run all checks and render the results as JSON or Markdown."""
from __future__ import annotations

import json
from collections import Counter

from botocore.exceptions import ClientError

from .client import error_code
from .ec2 import audit_ec2, audit_security_groups
from .iam import audit_iam
from .models import SEVERITY_ORDER, AuditConfig, AuditError, AuditReport, AuditResult
from .s3 import audit_s3


def run_audit(ec2, s3, iam, cfg: AuditConfig) -> AuditReport:
    """Run every check. A check that fails (e.g. AccessDenied) is recorded in ``errors``; the rest still run."""
    total = AuditResult()
    checks = [("ec2", audit_ec2, ec2), ("security-groups", audit_security_groups, ec2),
              ("s3", audit_s3, s3), ("iam", audit_iam, iam)]
    for name, fn, client in checks:
        try:
            total.extend(fn(client, cfg))
        except ClientError as exc:
            total.errors.append(AuditError(name, None, error_code(exc), str(exc)))
    findings = sorted(total.findings, key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.check, f.resource))
    errors = sorted(total.errors, key=lambda e: (e.check, e.resource or ""))
    return AuditReport(cfg.now, findings, errors)


def to_json(report: AuditReport) -> str:
    by_sev = Counter(f.severity for f in report.findings)
    doc = {
        "generated_at": report.generated_at.isoformat(),
        "summary": {"total": len(report.findings), "by_severity": dict(sorted(by_sev.items())),
                    "errors": len(report.errors)},
        "findings": [
            {"check": f.check, "resource": f.resource, "severity": f.severity,
             "message": f.message, "details": f.details}
            for f in report.findings
        ],
        "errors": [{"check": e.check, "resource": e.resource, "code": e.code, "message": e.message}
                   for e in report.errors],
    }
    return json.dumps(doc, indent=2, sort_keys=True)


def _cell(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def to_markdown(report: AuditReport) -> str:
    lines = ["# AWS audit report", "", f"Generated at: {report.generated_at.isoformat()}", ""]
    if report.findings:
        lines += ["## Findings", "", "| Severity | Check | Resource | Message |", "| --- | --- | --- | --- |"]
        lines += [f"| {_cell(f.severity)} | {_cell(f.check)} | {_cell(f.resource)} | {_cell(f.message)} |"
                  for f in report.findings]
    else:
        lines += ["## Findings", "", "No findings."]
    if report.errors:
        lines += ["", "## Errors (checks that could not complete)", "",
                  "| Check | Resource | Code | Message |", "| --- | --- | --- | --- |"]
        lines += [f"| {_cell(e.check)} | {_cell(e.resource or '-')} | {_cell(e.code)} | {_cell(e.message)} |"
                  for e in report.errors]
    return "\n".join(lines) + "\n"
