"""Text and JSON renderers (starter)."""

from __future__ import annotations

import json  # noqa: F401

from lab.engine import Report
from lab.models import Severity  # noqa: F401


def render_text(report: Report) -> str:
    """Render for humans. Exact format (the tests pin it):

    * one line per finding: ``{file}:{line}: {SEVERITY} {rule_id}: {message}  ({path})`` - with two spaces before the
      parenthesis, upper-case severity, and just ``{file}:`` (no line number) when ``line is None``;
    * then one line ``error: {text}`` per entry of ``report.errors``;
    * then a summary: ``{n} finding(s) in {files} file(s)`` or, with no findings, ``No findings in {files} file(s)``;
    * every line ends with a newline.

    TODO.
    """
    raise NotImplementedError("TODO: implement render_text")


def render_json(report: Report) -> str:
    """Render for machines: ``json.dumps(payload, indent=2) + "\\n"`` with::

        {"summary": {"files": 1, "findings": 3, "by_severity": {"critical": 0, "high": 1, "medium": 2, "low": 0}},
         "findings": [Finding.to_dict(), ...],
         "errors": ["..."]}

    ``by_severity`` always has all four keys in the order critical, high, medium, low. TODO.
    """
    raise NotImplementedError("TODO: implement render_json")
