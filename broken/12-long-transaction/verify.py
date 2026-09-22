#!/usr/bin/env python3
"""Verifier for broken/12-long-transaction.  Usage: python verify.py   (BROKEN_TARGET=solution for the reference)

Deterministic and sleep-free. Instead of racing threads, a probe runs INSIDE every enrich() call (that is
the "slow partner API" moment) and tries to take the write lock from a second connection with timeout=0.
If the worker holds a write transaction across enrich(), the probe gets SQLITE_BUSY -> not fixed.
"""
import importlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
TARGET = HERE / ("solution" if os.environ.get("BROKEN_TARGET") == "solution" else "app")
checks = []


def check(name, ok, detail=""):
    checks.append({"name": name, "ok": bool(ok), "detail": detail})
    return bool(ok)


def finish():
    fixed = all(c["ok"] for c in checks) and bool(checks)
    score = 100 if fixed else min(99, round(100 * sum(c["ok"] for c in checks) / max(1, len(checks))))
    print(json.dumps({"fixed": fixed, "checks": checks, "score": score}, indent=2))
    sys.exit(0 if fixed else 1)


PAYLOADS = ["alpha", "beta", "boom", "delta", "epsilon", "zeta"]


def main():
    tmp = Path(tempfile.mkdtemp(prefix="broken12-"))
    try:
        work = tmp / "app"
        shutil.copytree(TARGET, work, ignore=shutil.ignore_patterns("__pycache__"))
        sys.path.insert(0, str(work))
        try:
            qw = importlib.import_module("queue_worker")
        except Exception as e:  # noqa: BLE001
            check("app imports", False, repr(e))
            return finish()
        db = str(tmp / "app.db")
        qw.init_db(db)
        for p in PAYLOADS:
            qw.enqueue(db, p)

        calls, probes = [], []

        def enrich(payload):
            calls.append(payload)
            # --- probe: can ANOTHER writer get in while this slow call is in flight?
            other = sqlite3.connect(db, timeout=0, isolation_level=None)
            try:
                other.execute("BEGIN IMMEDIATE")
                other.execute("INSERT INTO events(name) VALUES (?)", ("probe-during-" + payload,))
                other.execute("COMMIT")
                probes.append((payload, True))
            except sqlite3.OperationalError as e:
                probes.append((payload, False))
                if other.in_transaction:
                    other.execute("ROLLBACK")
            finally:
                other.close()
            if payload == "boom":
                raise RuntimeError("partner API 500")
            return payload.upper() + "!"

        try:
            handled = qw.process_pending(db, enrich)
        except Exception as e:  # noqa: BLE001
            check("process_pending runs", False, repr(e))
            return finish()

        blocked = [p for p, ok in probes if not ok]
        check("no write lock held while the slow enrich() call is in flight",
              len(probes) == len(PAYLOADS) and not blocked,
              f"writers blocked during enrich() of: {blocked}" if blocked else f"{len(probes)} probes wrote fine")

        conn = sqlite3.connect(db)
        rows = {r[0]: r[1:] for r in conn.execute("SELECT payload, status, result, error FROM jobs")}
        good = all(rows.get(p) == ("done", p.upper() + "!", None) for p in PAYLOADS if p != "boom")
        bad = rows.get("boom") == ("failed", None, "partner API 500")
        check("every job processed with the right result; the failing job is marked failed with its error",
              good and bad and handled == len(PAYLOADS), f"handled={handled}")
        check("enrich() called exactly once per job", sorted(calls) == sorted(PAYLOADS), str(calls))
        n_events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        check("web-tier writes made during the batch were not lost", n_events == sum(ok for _, ok in probes),
              f"events={n_events}")
        conn.close()

        # idempotent: a second run has nothing to do
        calls.clear()
        again = qw.process_pending(db, enrich)
        check("second run is a no-op (no job processed twice)", again == 0 and not calls, f"calls={calls}")

        # a fresh job enqueued later is still picked up, and record_event still works afterwards
        qw.enqueue(db, "late")
        calls.clear()
        qw.process_pending(db, enrich)
        qw.record_event(db, "after-batch")
        conn = sqlite3.connect(db)
        late = conn.execute("SELECT status, result FROM jobs WHERE payload='late'").fetchone()
        conn.close()
        check("later jobs are processed and record_event() still works", late == ("done", "LATE!"), str(late))
    finally:
        try:
            sys.path.remove(str(tmp / "app"))
        except ValueError:
            pass
        shutil.rmtree(tmp, ignore_errors=True)
    finish()


if __name__ == "__main__":
    main()
