"""The fixture corpus: good files are clean, bad files produce exactly the expected (rule, path, line) triples."""

from __future__ import annotations

from helpers import fixture_text
from lab.engine import audit_text


def triples(name: str) -> list[tuple[str, str, int | None]]:
    report = audit_text(fixture_text(name), name)
    assert report.errors == [], report.errors
    return [(f.rule_id, f.path, f.line) for f in report.findings]


def test_well_configured_files_have_no_findings() -> None:
    assert triples("compose_good.yml") == []
    assert triples("k8s_good.yaml") == []


def test_compose_bad_findings_have_exact_rule_pointer_and_line() -> None:
    assert triples("compose_bad.yml") == [
        ("missing-probes", "/services/web", 2),
        ("resource-limits", "/services/web", 2),
        ("no-latest-tag", "/services/web/image", 3),
        ("no-exposed-ports", "/services/web/ports/0", 5),
        ("no-privileged", "/services/web/privileged", 6),
        ("no-plaintext-secrets", "/services/web/environment/DB_PASSWORD", 8),
        ("no-latest-tag", "/services/db/image", 11),
        ("no-plaintext-secrets", "/services/db/environment/0", 15),
    ]


def test_multi_document_k8s_file_reports_absolute_lines_per_document() -> None:
    assert triples("k8s_bad.yaml") == [
        ("missing-probes", "/spec/template/spec/containers/0", 9),
        ("no-latest-tag", "/spec/template/spec/containers/0/image", 10),
        ("no-privileged", "/spec/template/spec/containers/0/securityContext/privileged", 12),
        ("no-exposed-ports", "/spec/template/spec/containers/0/ports/0", 14),
        ("no-plaintext-secrets", "/spec/template/spec/containers/0/env/0/value", 18),
        ("resource-limits", "/spec/template/spec/containers/0/resources/limits", 20),
        ("missing-probes", "/spec/containers/0", 29),
        ("resource-limits", "/spec/containers/0", 29),
        ("no-latest-tag", "/spec/containers/0/image", 30),
    ]


def test_yaml_anchors_and_merge_keys_are_resolved_and_point_at_the_anchor_line() -> None:
    # 'worker' inherits image busybox:latest from the anchor (line 2); 'cron' overrides it with a pinned tag.
    assert triples("compose_anchors.yml") == [("no-latest-tag", "/services/worker/image", 2)]
