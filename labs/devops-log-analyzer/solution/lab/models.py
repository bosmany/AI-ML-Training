"""Plain data containers shared by the parser, the analyzer and the renderers."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class LogEntry:
    ip: str
    timestamp: datetime  # timezone-aware
    method: str
    path: str  # query string removed
    status: int
    bytes_sent: int
    request_time: float | None  # seconds; None when the line has no request_time field


@dataclass
class ParseStats:
    """Counters filled in by ``iter_entries`` while the stream is consumed."""

    parsed: int = 0
    skipped: int = 0


@dataclass(frozen=True)
class HourStat:
    hour: str  # "2024-03-10T14" (UTC)
    total: int
    errors: int  # 5xx responses

    @property
    def error_rate(self) -> float:
        return self.errors / self.total if self.total else 0.0


@dataclass(frozen=True)
class Suspect:
    ip: str
    failures: int  # total 401/403 responses seen for this IP
    first_flagged_at: datetime


@dataclass
class Report:
    parsed: int = 0
    skipped: int = 0
    error_rate: float = 0.0  # overall 5xx / parsed
    top_ips: list[tuple[str, int]] = field(default_factory=list)
    top_paths: list[tuple[str, int]] = field(default_factory=list)
    hourly: list[HourStat] = field(default_factory=list)  # sorted by hour
    latency: dict[str, float | None] = field(default_factory=dict)  # p50/p95/p99
    suspicious: list[Suspect] = field(default_factory=list)  # sorted by ip

    def to_dict(self) -> dict:
        d = asdict(self)
        d["hourly"] = [
            {"hour": h.hour, "total": h.total, "errors": h.errors, "error_rate": round(h.error_rate, 6)}
            for h in self.hourly
        ]
        d["top_ips"] = [{"ip": ip, "count": n} for ip, n in self.top_ips]
        d["top_paths"] = [{"path": p, "count": n} for p, n in self.top_paths]
        d["suspicious"] = [
            {"ip": s.ip, "failures": s.failures, "first_flagged_at": s.first_flagged_at.isoformat()}
            for s in self.suspicious
        ]
        d["error_rate"] = round(self.error_rate, 6)
        return d
