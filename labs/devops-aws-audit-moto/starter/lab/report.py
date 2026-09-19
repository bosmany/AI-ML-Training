"""Run all checks and render the results as JSON or Markdown."""
from __future__ import annotations

from .models import SEVERITY_ORDER, AuditConfig, AuditReport


def run_audit(ec2, s3, iam, cfg: AuditConfig) -> AuditReport:
    """Run audit_ec2, audit_security_groups, audit_s3, audit_iam and merge the ``AuditResult`` objects.

    TODO:
    - if a whole check raises ClientError (e.g. AccessDenied on list_users), append
      ``AuditError(<"ec2"|"security-groups"|"s3"|"iam">, None, code, message)`` and keep going.
    - findings sorted by (SEVERITY_ORDER[severity], check, resource); errors by (check, resource or "").
    - ``AuditReport.generated_at`` is ``cfg.now`` (never call datetime.now() here).
    """
    raise NotImplementedError


def to_json(report: AuditReport) -> str:
    """JSON document (indent=2, sort_keys=True) with keys: generated_at (iso), summary
    {"total", "by_severity" {sev: count}, "errors"}, findings [{check, resource, severity, message,
    details}], errors [{check, resource, code, message}]. Must be deterministic."""
    raise NotImplementedError


def to_markdown(report: AuditReport) -> str:
    """Markdown starting with "# AWS audit report". Findings as a table with header
    "| Severity | Check | Resource | Message |" (or the sentence "No findings." when empty), then an
    "Errors" section table when there are errors. Escape "|" as "\\|" and flatten newlines in cells."""
    raise NotImplementedError
