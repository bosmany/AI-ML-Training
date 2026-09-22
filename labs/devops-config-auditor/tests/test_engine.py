"""Engine: config, severity override, crashing rules, parse errors, safe loading, exit codes."""

from __future__ import annotations

from pathlib import Path

import pytest

from helpers import compose, fixture_text
from lab.engine import AuditConfig, ConfigError, Report, audit_paths, audit_text, parse_config
from lab.models import Document, Finding, Severity
from lab.rule import Rule
from lab.rules import DEFAULT_RULES, NoLatestTag

IDS = [r.id for r in DEFAULT_RULES]
BAD = compose("image: nginx:latest\nprivileged: true")


class Boom(Rule):
    id = "boom"
    severity = Severity.LOW
    description = "always crashes"

    def check(self, doc: Document) -> list[Finding]:
        raise RuntimeError("kaboom")


def test_at_least_five_rules_ship_with_unique_ids_and_metadata() -> None:
    assert len(DEFAULT_RULES) >= 5
    assert len(set(IDS)) == len(IDS)
    for rule in DEFAULT_RULES:
        assert rule.description and isinstance(rule.severity, Severity)
    assert {"no-latest-tag", "no-privileged", "no-plaintext-secrets", "resource-limits", "missing-probes"} <= set(IDS)
    assert audit_text(BAD, "a.yml").findings, "the default rule set must find problems in a bad file"


def test_parse_config_reads_disable_and_severity_override() -> None:
    cfg = parse_config("rules:\n  no-latest-tag: {enabled: false}\n  missing-probes: {severity: HIGH}\n  no-privileged:\n", IDS)
    assert cfg.disabled == {"no-latest-tag"}
    assert cfg.severities == {"missing-probes": Severity.HIGH}
    assert parse_config("", IDS) == AuditConfig() and parse_config("rules:\n", IDS) == AuditConfig()


def test_parse_config_rejects_unknown_rule_ids_severities_and_shapes() -> None:
    for bad in [
        "rules:\n  no-such-rule: {enabled: false}\n",
        "rules:\n  no-latest-tag: {severity: urgent}\n",
        "rules:\n  no-latest-tag: {colour: red}\n",
        "rules: [no-latest-tag]\n",
        "unknown_top_level: 1\n",
        "rules: [unclosed\n",
    ]:
        with pytest.raises(ConfigError):
            parse_config(bad, IDS)


def test_disabled_rules_do_not_run_and_severity_overrides_apply() -> None:
    base = {f.rule_id: f.severity for f in audit_text(BAD, "a.yml").findings}
    assert base["no-latest-tag"] == Severity.MEDIUM and "no-privileged" in base
    cfg = AuditConfig(disabled=frozenset({"no-privileged"}), severities={"no-latest-tag": Severity.CRITICAL})
    after = {f.rule_id: f.severity for f in audit_text(BAD, "a.yml", config=cfg).findings}
    assert "no-privileged" not in after
    assert after["no-latest-tag"] == Severity.CRITICAL


def test_a_crashing_rule_is_reported_as_an_error_not_a_silent_pass() -> None:
    report = audit_text(BAD, "a.yml", rules=[Boom(), NoLatestTag()])
    assert any("boom" in e and "kaboom" in e for e in report.errors), report.errors
    assert [f.rule_id for f in report.findings] == ["no-latest-tag"], "other rules still run"
    assert report.exit_code(Severity.CRITICAL) == 2, "an internal error must fail the run"


def test_invalid_yaml_is_an_error_with_file_line_and_column_and_other_files_are_still_audited(tmp_path: Path) -> None:
    (tmp_path / "a_bad.yml").write_text("services:\n  web: [unclosed\n", encoding="utf-8")
    (tmp_path / "b_ok.yml").write_text(BAD, encoding="utf-8")
    report = audit_paths([tmp_path / "a_bad.yml", tmp_path / "b_ok.yml"])
    assert report.files == 2
    assert len(report.errors) == 1 and report.errors[0].startswith(f"{tmp_path / 'a_bad.yml'}:")
    parts = report.errors[0].removeprefix(str(tmp_path / "a_bad.yml") + ":").split(":", 2)
    assert parts[0].isdigit() and parts[1].isdigit(), f"expected 'file:line:column: message', got {report.errors[0]!r}"
    assert report.findings, "the valid file must still be audited"


def test_only_safe_yaml_is_loaded_python_tags_never_execute(tmp_path: Path) -> None:
    marker = tmp_path / "pwned"
    evil = f'services:\n  web: !!python/object/apply:os.system ["touch {marker}"]\n'
    report = audit_text(evil, "evil.yml")
    assert not marker.exists(), "a config file executed code: use yaml.safe_load / SafeLoader only"
    assert report.errors, "python-specific tags must be rejected as errors"


def test_empty_files_and_odd_shapes_do_not_crash_and_directories_are_expanded(tmp_path: Path) -> None:
    for text in ["", "# only a comment\n", "---\n---\n", "[1, 2, 3]\n", "services: [1, 2]\n", "services:\n  web: 5\n", "kind: Deployment\n", "just a string\n"]:
        report = audit_text(text, "odd.yml")
        assert (report.findings, report.errors) == ([], []), f"{text!r} -> {report}"
    sub = tmp_path / "deploy" / "nested"
    sub.mkdir(parents=True)
    (sub / "x.yaml").write_text(BAD, encoding="utf-8")
    (tmp_path / "deploy" / "b.yml").write_text(BAD, encoding="utf-8")
    (tmp_path / "deploy" / "notes.txt").write_text("services: bad: [", encoding="utf-8")
    report = audit_paths([tmp_path / "deploy"])
    assert report.files == 2 and report.errors == []
    assert [Path(f.file).name for f in report.findings if f.rule_id == "no-privileged"] == ["b.yml", "x.yaml"]


def test_json_files_are_audited_too(tmp_path: Path) -> None:
    p = tmp_path / "compose.json"
    p.write_text('{"services": {"web": {"image": "nginx:latest"}}}', encoding="utf-8")
    report = audit_paths([p], rules=[NoLatestTag()])
    assert [(f.path, f.line) for f in report.findings] == [("/services/web/image", 1)]


def test_exit_code_reflects_fail_on_threshold_and_errors() -> None:
    clean = audit_text(fixture_text("compose_good.yml"), "g.yml")
    medium_only = audit_text(compose("image: a:latest\nmem_limit: 1m\nhealthcheck: {test: ['CMD', 'true']}"), "m.yml")
    assert [f.severity for f in medium_only.findings] == [Severity.MEDIUM]
    assert clean.exit_code(Severity.LOW) == 0
    assert medium_only.exit_code(Severity.HIGH) == 0
    assert medium_only.exit_code(Severity.MEDIUM) == 1, "at the threshold counts"
    assert medium_only.exit_code(Severity.LOW) == 1
    assert audit_text(BAD, "b.yml").exit_code(Severity.CRITICAL) == 1
    assert Report(errors=["boom"]).exit_code(Severity.CRITICAL) == 2
