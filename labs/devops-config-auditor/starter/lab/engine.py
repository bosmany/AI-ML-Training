"""Rule engine, configuration and exit codes (starter)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import yaml  # noqa: F401

from lab.loader import load_documents  # noqa: F401
from lab.models import ConfigParseError, Document, Finding, Severity  # noqa: F401
from lab.rule import Rule
from lab.rules import DEFAULT_RULES  # noqa: F401

CONFIG_SUFFIXES = {".yml", ".yaml", ".json"}
EXIT_OK, EXIT_FINDINGS, EXIT_ERROR = 0, 1, 2


class ConfigError(ValueError):
    """Bad auditor configuration (unknown rule id, unknown severity, wrong shape). (Provided.)"""


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
        """2 if ``errors`` is not empty, else 1 if any finding has ``severity >= fail_on``, else 0.

        TODO. Errors win: a file that could not be audited must never look like a clean pass in CI.
        """
        raise NotImplementedError("TODO: implement Report.exit_code")


def parse_config(text: str, known_rule_ids: Iterable[str]) -> AuditConfig:
    """Parse the contents of an ``.auditor.yaml``::

        rules:
          no-latest-tag: {enabled: false}
          missing-probes: {severity: high}

    TODO: ``yaml.safe_load`` ONLY. Empty file / ``rules:`` with nothing -> ``AuditConfig()``. Raise ``ConfigError``
    for: invalid YAML, a top level that is not a mapping with only the key ``rules``, ``rules`` that is not a
    mapping, an UNKNOWN rule id (the message must contain the id), options other than ``enabled`` / ``severity``,
    and an invalid severity (use ``Severity.parse``, case-insensitive). ``enabled: false`` disables a rule.
    """
    raise NotImplementedError("TODO: implement parse_config")


def run_rules(
    doc: Document, rules: Sequence[Rule], config: AuditConfig | None = None
) -> tuple[list[Finding], list[str]]:
    """Run every enabled rule on one document; return ``(findings, errors)``.

    TODO: skip rules whose id is in ``config.disabled``; apply ``config.severities`` overrides
    (``dataclasses.replace(finding, severity=...)`` - Finding is frozen); and if a rule RAISES, catch the exception
    and add an error string containing the rule id and the exception message - a crashing rule must be visible,
    never a silent "no findings", and must not stop the other rules.
    """
    raise NotImplementedError("TODO: implement run_rules")


def audit_text(
    text: str, filename: str, rules: Sequence[Rule] | None = None, config: AuditConfig | None = None
) -> Report:
    """Audit YAML/JSON text (every document in it) and return a Report with ``files == 1``.

    TODO: ``rules=None`` means ``DEFAULT_RULES``. ``load_documents`` raises ``ConfigParseError`` for invalid
    YAML: put ``str(exc)`` (``file:line:col: message``) into ``report.errors`` instead of raising.
    Sort findings by ``(file, line or 0, path, rule_id)`` so output is deterministic.
    """
    raise NotImplementedError("TODO: implement audit_text")


def collect_files(paths: Iterable[Path]) -> list[Path]:
    """Files as given; each directory expands recursively (sorted) to its ``CONFIG_SUFFIXES`` files. TODO."""
    raise NotImplementedError("TODO: implement collect_files")


def audit_paths(
    paths: Iterable[Path], rules: Sequence[Rule] | None = None, config: AuditConfig | None = None
) -> Report:
    """Audit files/directories and merge the results (``report.files`` counts every collected file).

    TODO: read each file as UTF-8; an unreadable file (missing, permissions, bad encoding) is an entry in
    ``errors`` mentioning the path - the other files are still audited. Sort the merged findings as above.
    """
    raise NotImplementedError("TODO: implement audit_paths")

