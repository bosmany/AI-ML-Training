"""Small helpers shared by the test modules."""

from __future__ import annotations

import textwrap
from pathlib import Path

from lab.engine import audit_text
from lab.models import Finding

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def run_rule(rule_cls: type, yaml_text: str, filename: str = "t.yml") -> list[Finding]:
    """Findings of ONE rule for an inline YAML snippet (fails loudly if the snippet cannot be audited)."""
    report = audit_text(textwrap.dedent(yaml_text), filename, rules=[rule_cls()])
    assert report.errors == [], report.errors
    return report.findings


def compose(service_body: str) -> str:
    """Wrap indented service attributes into a compose file with one service called ``app`` (body at 4 spaces)."""
    return "services:\n  app:\n" + textwrap.indent(textwrap.dedent(service_body).strip("\n"), "    ") + "\n"


def k8s(container_body: str, kind: str = "Deployment") -> str:
    """A minimal workload with one container ``c`` whose extra attributes are ``container_body``."""
    head = {
        "Deployment": "apiVersion: apps/v1\nkind: Deployment\nspec:\n  template:\n    spec:\n      containers:\n",
        "Job": "apiVersion: batch/v1\nkind: Job\nspec:\n  template:\n    spec:\n      containers:\n",
    }[kind]
    extra = textwrap.indent(textwrap.dedent(container_body).strip("\n"), "  ")
    body = textwrap.indent("- name: c\n" + extra, "        ")
    return head + body + "\n"
