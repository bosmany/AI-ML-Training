"""SQLite schema and connection helper (scaffold - provided).

Everything is real, durable SQLite: open a second Tracker/Registry on the same file and you see the same data.
ALWAYS pass values as ``?`` parameters - never build SQL with f-strings.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id       TEXT PRIMARY KEY,
    experiment   TEXT NOT NULL,
    name         TEXT,
    status       TEXT NOT NULL,
    start_time   TEXT NOT NULL,
    end_time     TEXT,
    dataset_hash TEXT,
    code_version TEXT
);
CREATE TABLE IF NOT EXISTS params (
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    key    TEXT NOT NULL,
    value  TEXT NOT NULL,
    PRIMARY KEY (run_id, key)
);
CREATE TABLE IF NOT EXISTS metrics (
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    key    TEXT NOT NULL,
    step   INTEGER NOT NULL,
    value  REAL NOT NULL,
    PRIMARY KEY (run_id, key, step)
);
CREATE TABLE IF NOT EXISTS tags (
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    key    TEXT NOT NULL,
    value  TEXT NOT NULL,
    PRIMARY KEY (run_id, key)
);
CREATE TABLE IF NOT EXISTS artifacts (
    run_id     TEXT NOT NULL REFERENCES runs(run_id),
    name       TEXT NOT NULL,
    sha256     TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    PRIMARY KEY (run_id, name)
);
CREATE TABLE IF NOT EXISTS model_versions (
    model      TEXT NOT NULL,
    version    INTEGER NOT NULL,
    run_id     TEXT NOT NULL REFERENCES runs(run_id),
    stage      TEXT NOT NULL,
    validated  INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    PRIMARY KEY (model, version)
);
CREATE TABLE IF NOT EXISTS quality_flags (
    flag_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    model       TEXT NOT NULL,
    version     INTEGER NOT NULL,
    description TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'open',   -- 'open' | 'resolved'
    created_at  TEXT NOT NULL,
    resolved_at TEXT
);
CREATE TABLE IF NOT EXISTS stage_history (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    model      TEXT NOT NULL,
    version    INTEGER NOT NULL,
    from_stage TEXT NOT NULL,
    to_stage   TEXT NOT NULL,
    reason     TEXT NOT NULL,
    at         TEXT NOT NULL
);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    """Open (creating if needed) the database file with rows addressable by column name."""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def utcnow() -> datetime:
    return datetime.now(UTC)


def to_iso(moment: datetime) -> str:
    """Fixed-width UTC text that sorts chronologically as a plain string."""
    return moment.astimezone(UTC).isoformat(timespec="microseconds")


def from_iso(text: str) -> datetime:
    return datetime.fromisoformat(text)
