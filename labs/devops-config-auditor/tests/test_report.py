"""Text and JSON renderers."""

from __future__ import annotations

import json

from helpers import fixture_text
from lab.engine import Report, audit_text
from lab.models import Finding, Severity
from lab.report import render_json, render_text


def test_text_report_has_one_line_per_finding_and_a_summary() -> None:
    report = Report(
        findings=[
            Finding("no-latest-tag", Severity.MEDIUM, "image 'nginx:latest' uses tag ':latest'", "app.yml", "/services/web/image", 3),
            Finding("no-privileged", Severity.CRITICAL, "'web' runs privileged", "app.yml", "/services/web", None),
        ],
        files=1,
    )
    assert render_text(report) == (
        "app.yml:3: MEDIUM no-latest-tag: image 'nginx:latest' uses tag ':latest'  (/services/web/image)\n"
        "app.yml: CRITICAL no-privileged: 'web' runs privileged  (/services/web)\n"
        "2 finding(s) in 1 file(s)\n"
    )


def test_text_report_for_clean_runs_and_errors() -> None:
    assert render_text(Report(files=3)) == "No findings in 3 file(s)\n"
    text = render_text(Report(errors=["bad.yml:2:5: oops"], files=1))
    assert text.splitlines()[0] == "error: bad.yml:2:5: oops"


def test_json_report_structure_and_counts() -> None:
    report = audit_text(fixture_text("compose_bad.yml"), "compose_bad.yml")
    data = json.loads(render_json(report))
    assert data["summary"] == {
        "files": 1,
        "findings": 8,
        "by_severity": {"critical": 1, "high": 2, "medium": 4, "low": 1},
    }
    first = data["findings"][0]
    assert set(first) == {"rule_id", "severity", "message", "file", "path", "line"}
    assert (first["rule_id"], first["severity"], first["path"], first["line"]) == ("missing-probes", "low", "/services/web", 2)
    assert data["errors"] == []


def test_findings_are_sorted_by_file_then_line_and_output_is_deterministic() -> None:
    a = audit_text(fixture_text("k8s_bad.yaml"), "k.yaml")
    b = audit_text(fixture_text("k8s_bad.yaml"), "k.yaml")
    assert render_json(a) == render_json(b)
    lines = [f.line for f in a.findings]
    assert lines == sorted(lines)
