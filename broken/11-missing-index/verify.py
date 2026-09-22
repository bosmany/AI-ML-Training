#!/usr/bin/env python3
"""Verifier for broken/11-missing-index.  Usage: python verify.py   (BROKEN_TARGET=solution to check the reference)

Deterministic: it does NOT rely on wall-clock time. The "time budget" is SQLite VM instructions executed
(sqlite3 progress handler), plus the EXPLAIN QUERY PLAN of every statement the app really runs.
"""
import importlib
import json
import os
import random
import re
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
TARGET = HERE / ("solution" if os.environ.get("BROKEN_TARGET") == "solution" else "app")
checks = []

N_ROWS, N_CUSTOMERS = 150_000, 3_000
VM_BUDGET = 3_000          # VM instructions per call; a full scan of 150k rows costs > 500k
SAMPLE_CUSTOMERS = (0, 7, 1234, 2048, 2999)


def check(name, ok, detail=""):
    checks.append({"name": name, "ok": bool(ok), "detail": detail})
    return bool(ok)


def finish():
    fixed = all(c["ok"] for c in checks) and bool(checks)
    score = 100 if fixed else min(99, round(100 * sum(c["ok"] for c in checks) / max(1, len(checks))))
    print(json.dumps({"fixed": fixed, "checks": checks, "score": score}, indent=2))
    sys.exit(0 if fixed else 1)


def data_rows():  # verifier's own copy of the data: the learner cannot shrink the table
    rng = random.Random(11)
    for i in range(1, N_ROWS + 1):
        yield (i, rng.randrange(N_CUSTOMERS), rng.choice(("open", "shipped", "shipped", "cancelled")),
               rng.randrange(500, 50_000), 1_700_000_000 + i * 37)


def measure(conn, fn):
    """Run fn(); return (result, vm_instructions, executed_sql_statements)."""
    steps, stmts = [0], []
    conn.set_progress_handler(lambda: steps.__setitem__(0, steps[0] + 1) or 0, 10)
    conn.set_trace_callback(stmts.append)
    try:
        res = fn()
    finally:
        conn.set_progress_handler(None, 0)
        conn.set_trace_callback(None)
    return res, steps[0] * 10, stmts


def main():
    tmp = Path(tempfile.mkdtemp(prefix="broken11-"))
    try:
        work = tmp / "app"
        shutil.copytree(TARGET, work, ignore=shutil.ignore_patterns("__pycache__"))
        sys.path.insert(0, str(work))
        try:
            schema = importlib.import_module("schema")
            orders = importlib.import_module("orders")
        except Exception as e:  # noqa: BLE001
            check("app imports", False, repr(e))
            return finish()

        conn = sqlite3.connect(tmp / "shop.db")
        try:
            schema.apply(conn)
        except Exception as e:  # noqa: BLE001
            check("schema.apply() runs on an empty database", False, repr(e))
            return finish()
        cols = [r[1] for r in conn.execute("PRAGMA table_info(orders)")]
        check("orders table keeps its columns",
              cols == ["id", "customer_id", "status", "total_cents", "created_at"], str(cols))
        rows = list(data_rows())
        conn.executemany("INSERT INTO orders VALUES (?,?,?,?,?)", rows)
        conn.commit()

        # ---- behaviour preserved: results equal an independent pure-python computation
        ok_behaviour, ok_plan, ok_budget = True, True, True
        worst_steps, plan_notes = 0, []
        for cid in SAMPLE_CUSTOMERS:
            mine = sorted((r for r in rows if r[1] == cid), key=lambda r: (r[4], r[0]), reverse=True)
            expect_recent = [(r[0], r[3], r[4]) for r in mine[:20]]
            live = [r for r in mine if r[2] != "cancelled"]
            expect_sum = (len(live), sum(r[3] for r in live))
            (recent, summary), steps, stmts = measure(
                conn, lambda: (orders.recent_orders(conn, cid), orders.customer_summary(conn, cid)))
            if [tuple(r) for r in recent] != expect_recent or tuple(summary) != expect_sum:
                ok_behaviour = False
            worst_steps = max(worst_steps, steps)
            if steps > 2 * VM_BUDGET:
                ok_budget = False
            for sql in stmts:
                if not re.search(r"\borders\b", sql, re.I):
                    continue
                plan = " | ".join(r[-1] for r in conn.execute("EXPLAIN QUERY PLAN " + sql))
                plan_notes.append(plan)
                if re.search(r"\bSCAN\b", plan) or "SEARCH" not in plan or "customer_id" not in plan:
                    ok_plan = False
        check("results identical to the reference computation (behaviour preserved)", ok_behaviour)
        check("EXPLAIN QUERY PLAN: every orders query is an index SEARCH on customer_id, no SCAN",
              ok_plan, sorted(set(plan_notes))[0] if plan_notes else "no statements captured")
        check(f"VM-instruction budget per page view <= {2 * VM_BUDGET} (a full table scan costs >500000)",
              ok_budget, f"worst={worst_steps}")

        # ---- the writes must still work (an index must not break inserts / schema)
        try:
            conn.execute("INSERT INTO orders VALUES (?,?,?,?,?)", (N_ROWS + 1, 7, "open", 100, 1_800_000_000))
            newest = orders.recent_orders(conn, 7)[0]
            check("new orders show up first", newest[0] == N_ROWS + 1)
        except Exception as e:  # noqa: BLE001
            check("new orders show up first", False, repr(e))
    finally:
        try:
            sys.path.remove(str(tmp / "app"))
        except ValueError:
            pass
        shutil.rmtree(tmp, ignore_errors=True)
    finish()


if __name__ == "__main__":
    main()
