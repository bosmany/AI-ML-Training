"""Try it yourself:  python app/bench.py   (builds a throw-away database in a temp dir)"""
import os
import sqlite3
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
import orders, schema, seed  # noqa: E402

with tempfile.TemporaryDirectory() as tmp:
    conn = sqlite3.connect(os.path.join(tmp, "shop.db"))
    schema.apply(conn)
    seed.load(conn)
    for cid in (7, 1234, 2999):
        t = time.perf_counter()
        recent = orders.recent_orders(conn, cid)
        summary = orders.customer_summary(conn, cid)
        ms = (time.perf_counter() - t) * 1000
        print(f"customer {cid}: {len(recent)} recent, summary={summary}, {ms:.1f} ms")
    print("plan:", conn.execute("EXPLAIN QUERY PLAN " + orders.RECENT_SQL, (7, 20)).fetchall())
