"""Turn a ``Report`` into text or JSON."""
from __future__ import annotations

import json

from .models import Report


def render_json(report: Report) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True)


def _fmt(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.3f}s"


def render_text(report: Report) -> str:
    lines = [
        f"Parsed lines : {report.parsed}",
        f"Skipped lines: {report.skipped}",
        f"5xx rate     : {report.error_rate:.2%}",
        "",
        "Latency (request_time): " + "  ".join(f"{k}={_fmt(v)}" for k, v in report.latency.items()),
        "",
        "Top IPs:",
        *(f"  {n:>6}  {ip}" for ip, n in report.top_ips),
        "",
        "Top paths:",
        *(f"  {n:>6}  {p}" for p, n in report.top_paths),
        "",
        "5xx per hour (UTC):",
        *(f"  {h.hour}  {h.errors}/{h.total}  {h.error_rate:.2%}" for h in report.hourly),
        "",
        "Suspicious IPs (auth-failure bursts):",
        *(
            [f"  {s.ip}  failures={s.failures}  first_flagged={s.first_flagged_at.isoformat()}" for s in report.suspicious]
            or ["  none"]
        ),
    ]
    return "\n".join(lines)
