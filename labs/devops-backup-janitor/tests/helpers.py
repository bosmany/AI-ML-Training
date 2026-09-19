from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

NOW = datetime(2024, 6, 30, 12, 0, 0, tzinfo=timezone.utc)


def days_ago(n: float, hour: int | None = None) -> datetime:
    t = NOW - timedelta(days=n)
    return t.replace(hour=hour, minute=0, second=0) if hour is not None else t


def make_backup(directory: Path, name: str, when: datetime, *, is_dir: bool = False) -> Path:
    """Create a fake backup and stamp its mtime (this is how real retention tools see 'age')."""
    p = directory / name
    if is_dir:
        p.mkdir()
        (p / "data.bin").write_text("x")
    else:
        p.write_text("backup-data")
    ts = when.timestamp()
    os.utime(p, (ts, ts))
    return p


def names(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.iterdir() if not p.name.startswith("."))
