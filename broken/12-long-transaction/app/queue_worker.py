"""Tiny job queue + event log on one SQLite file.

* the web handlers call `record_event()` (must be quick, many per second)
* a batch worker calls `process_pending()` every few minutes; for each job it calls `enrich(payload)`,
  which in production is a slow HTTP request to a partner API (0.3 - 3 s per call).
"""
import sqlite3

BUSY_TIMEOUT_S = 5


def connect(path):
    # isolation_level=None: we issue BEGIN/COMMIT ourselves so the transaction boundaries are explicit
    return sqlite3.connect(path, timeout=BUSY_TIMEOUT_S, isolation_level=None)


def init_db(path):
    conn = connect(path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id      INTEGER PRIMARY KEY,
            payload TEXT NOT NULL,
            status  TEXT NOT NULL DEFAULT 'pending',   -- pending | done | failed
            result  TEXT,
            error   TEXT
        );
        CREATE TABLE IF NOT EXISTS events (
            id   INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );
        """
    )
    conn.close()


def enqueue(path, payload):
    conn = connect(path)
    try:
        return conn.execute("INSERT INTO jobs(payload) VALUES (?)", (payload,)).lastrowid
    finally:
        conn.close()


def record_event(path, name):
    """Called by the web tier on every request."""
    conn = connect(path)
    try:
        conn.execute("INSERT INTO events(name) VALUES (?)", (name,))
    finally:
        conn.close()


def process_pending(path, enrich):
    """Enrich every pending job. A job whose enrich() raises is marked 'failed' (with the error text);
    the other jobs are still processed. Returns the number of jobs handled."""
    conn = connect(path)
    try:
        conn.execute("BEGIN IMMEDIATE")  # take the write lock up front so the whole batch is consistent
        jobs = conn.execute("SELECT id, payload FROM jobs WHERE status = 'pending' ORDER BY id").fetchall()
        for job_id, payload in jobs:
            try:
                result = enrich(payload)
            except Exception as exc:  # noqa: BLE001 - one bad job must not sink the batch
                conn.execute("UPDATE jobs SET status='failed', error=? WHERE id=?", (str(exc), job_id))
                continue
            conn.execute("UPDATE jobs SET status='done', result=? WHERE id=?", (result, job_id))
        conn.execute("COMMIT")
        return len(jobs)
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
