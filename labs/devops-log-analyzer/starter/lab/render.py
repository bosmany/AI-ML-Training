"""Turn a ``Report`` into text or JSON."""
from __future__ import annotations

from .models import Report


def render_json(report: Report) -> str:
    """Pretty JSON of ``report.to_dict()`` (``to_dict`` is already provided in models.py)."""
    raise NotImplementedError


def render_text(report: Report) -> str:
    """Human readable report. Show: parsed and skipped counts, overall 5xx rate as a percentage
    with two decimals (e.g. ``10.00%``), latency percentiles, top IPs, top paths, 5xx per hour
    and the suspicious IPs (or 'none')."""
    raise NotImplementedError
