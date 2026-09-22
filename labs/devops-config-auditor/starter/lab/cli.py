"""Command line interface (starter)."""

from __future__ import annotations

import argparse
import sys  # noqa: F401
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from lab.engine import EXIT_ERROR, AuditConfig, ConfigError, audit_paths, parse_config  # noqa: F401
from lab.models import Severity
from lab.report import render_json, render_text  # noqa: F401
from lab.rules import DEFAULT_RULES  # noqa: F401


def build_parser() -> argparse.ArgumentParser:
    """(Provided.)"""
    p = argparse.ArgumentParser(prog="auditor", description="Audit docker-compose and Kubernetes YAML.")
    p.add_argument("paths", nargs="+", type=Path, help="files or directories")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--fail-on", choices=[s.label for s in Severity], default="high", help="exit 1 at/above this")
    p.add_argument("--config", type=Path, help="path to an .auditor.yaml")
    return p


def main(argv: Sequence[str] | None = None, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    """Run the auditor and RETURN the exit code (never call ``sys.exit`` here; tests call ``main`` directly).

    Exit codes: 0 clean, 1 findings at/above ``--fail-on``, 2 usage / config / parse / internal error.

    TODO:
      * write to ``stdout`` / ``stderr`` when given, else ``sys.stdout`` / ``sys.stderr``;
      * ``parser.parse_args`` raises ``SystemExit`` on bad usage (code 2): turn that into a return value;
      * if ``--config`` is given, read it and ``parse_config(text, [r.id for r in DEFAULT_RULES])``; on
        ``ConfigError`` or ``OSError`` print ``config error: ...`` to stderr, print nothing to stdout, return 2;
      * ``audit_paths(args.paths, config=config)``, render as text or JSON to stdout, and return
        ``report.exit_code(Severity.parse(args.fail_on))``.
    """
    raise NotImplementedError("TODO: implement main")
