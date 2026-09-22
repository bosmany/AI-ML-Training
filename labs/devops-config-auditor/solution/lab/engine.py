"""Rule engine, configuration and exit codes (reference solution)."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from lab.loader import load_documents
from lab.models import ConfigParseError, Document, Finding, Severity
from lab.rule import Rule
from lab.rules import DEFAULT_RULES

CONFIG_SUFFIXES = {".yml", ".yaml", ".json"}
EXIT_OK, EXIT_FINDINGS, EXIT_ERROR = 0, 1, 2


class ConfigError(ValueError):
    """Bad auditor configuration (unknown rule id, unknown severity, wrong shape)."""


@dataclass(frozen=True)
class AuditConfig:
    disabled: frozenset[str] = frozenset()
    severities: dict[str, Severity] = field(default_factory=dict)


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)  # parse errors, unreadable files, crashing rules
    files: int = 0

    def exit_code(self, fail_on: Severity = Severity.HIGH) -> int:
        """2 if anything could not be audited, 1 if a finding is at/above ``fail_on``, else 0."""
        if self.errors:
            return EXIT_ERROR
        if any(f.severity >= fail_on for f in self.findings):
            return EXIT_FINDINGS
        return EXIT_OK


def parse_config(text: str, known_rule_ids: Iterable[str]) -> AuditConfig:
    """Parse ``.auditor.yaml``::

        rules:
          no-latest-tag: {enabled: false}
          missing-probes: {severity: high}
    """
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid config YAML: {exc}") from exc
    if raw is None:
        return AuditConfig()
    if not isinstance(raw, dict) or set(raw) - {"rules"}:
        raise ConfigError("config must be a mapping with a single top-level key 'rules'")
    rules = raw.get("rules") or {}
    if not isinstance(rules, dict):
        raise ConfigError("'rules' must be a mapping of rule id to options")
    known = set(known_rule_ids)
    disabled: set[str] = set()
    severities: dict[str, Severity] = {}
    for rule_id, options in rules.items():
        if rule_id not in known:
            raise ConfigError(f"unknown rule id {rule_id!r} in config (known: {', '.join(sorted(known))})")
        options = options or {}
        if not isinstance(options, dict) or set(options) - {"enabled", "severity"}:
            raise ConfigError(f"options for {rule_id!r} may only contain 'enabled' and 'severity'")
        if options.get("enabled", True) is False:
            disabled.add(rule_id)
        if "severity" in options:
            try:
                severities[rule_id] = Severity.parse(options["severity"])
            except ValueError as exc:
                raise ConfigError(f"{rule_id}: {exc}") from exc
    return AuditConfig(frozenset(disabled), severities)


def run_rules(
    doc: Document, rules: Sequence[Rule], config: AuditConfig | None = None
) -> tuple[list[Finding], list[str]]:
    """Run every enabled rule on one document. A rule that raises is reported as an error, never skipped silently."""
    config = config or AuditConfig()
    findings: list[Finding] = []
    errors: list[str] = []
    for rule in rules:
        if rule.id in config.disabled:
            continue
        try:
            found = rule.check(doc)
        except Exception as exc:  # noqa: BLE001 - a buggy rule must not take the whole audit down
            errors.append(f"{doc.file}: internal error in rule '{rule.id}': {type(exc).__name__}: {exc}")
            continue
        override = config.severities.get(rule.id)
        findings.extend(dataclasses.replace(f, severity=override) if override else f for f in found)
    return findings, errors


def _sort_key(f: Finding) -> tuple[str, int, str, str]:
    return (f.file, f.line or 0, f.path, f.rule_id)


def audit_text(
    text: str, filename: str, rules: Sequence[Rule] | None = None, config: AuditConfig | None = None
) -> Report:
    """Audit YAML/JSON text. A parse error becomes ``report.errors`` (with file:line:col), not an exception."""
    report = Report(files=1)
    try:
        docs = load_documents(text, filename)
    except ConfigParseError as exc:
        report.errors.append(str(exc))
        return report
    for doc in docs:
        found, errors = run_rules(doc, DEFAULT_RULES if rules is None else rules, config)
        report.findings.extend(found)
        report.errors.extend(errors)
    report.findings.sort(key=_sort_key)
    return report


def collect_files(paths: Iterable[Path]) -> list[Path]:
    """Files as given; directories expand (recursively, sorted) to their .yml/.yaml/.json files."""
    out: list[Path] = []
    for p in paths:
        if p.is_dir():
            out.extend(sorted(f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in CONFIG_SUFFIXES))
        else:
            out.append(p)
    return out


def audit_paths(
    paths: Iterable[Path], rules: Sequence[Rule] | None = None, config: AuditConfig | None = None
) -> Report:
    """Audit files/directories. One unreadable or invalid file is an error entry; the others are still audited."""
    report = Report()
    for path in collect_files(paths):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            report.files += 1
            report.errors.append(f"{path}: cannot read file: {exc}")
            continue
        sub = audit_text(text, str(path), rules, config)
        report.files += 1
        report.findings.extend(sub.findings)
        report.errors.extend(sub.errors)
    report.findings.sort(key=_sort_key)
    return report
