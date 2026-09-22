"""Command line interface (reference solution)."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from lab.engine import EXIT_ERROR, AuditConfig, ConfigError, audit_paths, parse_config
from lab.models import Severity
from lab.report import render_json, render_text
from lab.rules import DEFAULT_RULES


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="auditor", description="Audit docker-compose and Kubernetes YAML.")
    p.add_argument("paths", nargs="+", type=Path, help="files or directories")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--fail-on", choices=[s.label for s in Severity], default="high", help="exit 1 at/above this")
    p.add_argument("--config", type=Path, help="path to an .auditor.yaml")
    return p


def main(argv: Sequence[str] | None = None, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    """Exit codes: 0 clean, 1 findings at/above --fail-on, 2 usage/config/parse/internal error."""
    out, err = stdout or sys.stdout, stderr or sys.stderr
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:  # argparse exits with 2 on bad usage
        return int(exc.code or 0)
    config = AuditConfig()
    if args.config is not None:
        try:
            config = parse_config(args.config.read_text(encoding="utf-8"), [r.id for r in DEFAULT_RULES])
        except (ConfigError, OSError) as exc:
            print(f"config error: {exc}", file=err)
            return EXIT_ERROR
    report = audit_paths(args.paths, config=config)
    out.write(render_json(report) if args.format == "json" else render_text(report))
    return report.exit_code(Severity.parse(args.fail_on))
