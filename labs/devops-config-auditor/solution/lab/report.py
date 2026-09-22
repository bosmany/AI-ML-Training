"""Text and JSON renderers (reference solution)."""

from __future__ import annotations

import json

from lab.engine import Report
from lab.models import Severity


def render_text(report: Report) -> str:
    """One line per finding, then errors, then a summary::

        app.yml:3: MEDIUM no-latest-tag: image 'nginx:latest' uses tag ':latest'  (/services/web/image)
        error: bad.yml:2:5: mapping values are not allowed here
        1 finding(s) in 1 file(s)
    """
    lines = []
    for f in report.findings:
        where = f"{f.file}:{f.line}" if f.line is not None else f.file
        lines.append(f"{where}: {f.severity.label.upper()} {f.rule_id}: {f.message}  ({f.path})")
    lines.extend(f"error: {e}" for e in report.errors)
    if report.findings:
        lines.append(f"{len(report.findings)} finding(s) in {report.files} file(s)")
    else:
        lines.append(f"No findings in {report.files} file(s)")
    return "\n".join(lines) + "\n"


def render_json(report: Report) -> str:
    by_severity = {s.label: 0 for s in sorted(Severity, reverse=True)}
    for f in report.findings:
        by_severity[f.severity.label] += 1
    payload = {
        "summary": {"files": report.files, "findings": len(report.findings), "by_severity": by_severity},
        "findings": [f.to_dict() for f in report.findings],
        "errors": list(report.errors),
    }
    return json.dumps(payload, indent=2) + "\n"
