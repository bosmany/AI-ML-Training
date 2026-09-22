#!/usr/bin/env python3
"""Verifier for 06-n-plus-one.  Usage: python verify.py   (BROKEN_TARGET=solution to check the reference)"""
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_common"))
from harness import Verifier  # noqa: E402

MAX_STATEMENTS = 4


def reference_report(conn, customer_id):
    """The original, slow implementation: the definition of correct output."""
    customer = conn.execute("SELECT id, name FROM customers WHERE id = ?", (customer_id,)).fetchone()
    if customer is None:
        return None
    report = {"customer": {"id": customer["id"], "name": customer["name"]}, "orders": []}
    for o in conn.execute("SELECT id, created_at, status FROM orders WHERE customer_id = ? "
                          "ORDER BY created_at DESC, id DESC", (customer_id,)).fetchall():
        items = []
        for line in conn.execute("SELECT id, product_id, qty FROM order_items WHERE order_id = ? ORDER BY id", (o["id"],)).fetchall():
            p = conn.execute("SELECT name, price_cents FROM products WHERE id = ?", (line["product_id"],)).fetchone()
            items.append({"product_id": line["product_id"], "name": p["name"], "qty": line["qty"],
                          "unit_cents": p["price_cents"], "line_cents": p["price_cents"] * line["qty"]})
        report["orders"].append({"id": o["id"], "created_at": o["created_at"], "status": o["status"],
                                 "items": items, "total_cents": sum(i["line_cents"] for i in items)})
    return report


def probe_report():
    import json
    import random
    import tempfile
    import db
    import repo

    import atexit
    import shutil
    d = tempfile.mkdtemp()
    atexit.register(shutil.rmtree, d, True)
    path = os.path.join(d, "shop.db")
    conn = db.connect(path)
    db.init_schema(conn)
    rng = random.Random(5)
    conn.executemany("INSERT INTO customers VALUES (?,?)", [(1, "Ada"), (2, "Bob"), (3, "Cy"), (4, "Di")])
    conn.executemany("INSERT INTO products VALUES (?,?,?)", [(i, "product-%d" % i, 90 + i * 11) for i in range(1, 51)])
    oid = 0

    def add_orders(customer, n):
        nonlocal oid
        for _ in range(n):
            oid += 1
            conn.execute("INSERT INTO orders VALUES (?,?,?,?)",
                         (oid, customer, "2025-03-%02d" % rng.randint(1, 6), rng.choice(["paid", "new", "shipped"])))
            for _ in range(rng.choice([0, 0, 1, 2, 3, 5])):
                conn.execute("INSERT INTO order_items (order_id, product_id, qty) VALUES (?,?,?)",
                             (oid, rng.randint(1, 50), rng.randint(1, 4)))

    add_orders(2, 40)      # noise from another customer: must not leak into anyone's report
    add_orders(1, 20)      # small (customer 1)
    conn.commit()

    def measure(cid):
        seen = []
        conn.set_trace_callback(seen.append)
        got = repo.orders_report(conn, cid)
        conn.set_trace_callback(None)
        selects = [s for s in seen if s.lstrip().upper().startswith(("SELECT", "WITH"))]
        return got, len(selects)

    out = {}
    got, n_small = measure(1)
    out["small"] = {"statements": n_small, "same": got == reference_report(conn, 1), "orders": len(got["orders"])}
    add_orders(1, 380)     # now 400 orders
    conn.commit()
    got, n_big = measure(1)
    out["big"] = {"statements": n_big, "same": got == reference_report(conn, 1), "orders": len(got["orders"])}
    edge = {}
    for cid in (2, 3, 4, 999):
        got, _ = measure(cid)
        edge[str(cid)] = got == reference_report(conn, cid)
    out["edge"] = edge
    print(json.dumps(out))


def main():
    v = Verifier(__file__)
    o, err = v.probe(__file__, "report", timeout=40)
    if o is None:
        v.check("report runs", False, err)
    else:
        s, b = o["small"], o["big"]
        v.check("statement count does not grow with the data (%d orders vs %d)" % (s["orders"], b["orders"]),
                s["statements"] == b["statements"], "%d statements for %d orders, %d for %d orders" % (
                    s["statements"], s["orders"], b["statements"], b["orders"]))
        v.check("at most %d statements per report" % MAX_STATEMENTS, b["statements"] <= MAX_STATEMENTS,
                "%d statements" % b["statements"])
        v.check("output identical to the original (order, ties, empty orders, totals)", s["same"] and b["same"],
                "small=%s big=%s" % (s["same"], b["same"]))
        v.check("edge customers identical (other customer, no orders, unknown id)", all(o["edge"].values()), str(o["edge"]))
    v.pytest()
    v.finish()


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--probe":
        sys.path.insert(0, os.environ["BROKEN_TARGET_DIR"])
        globals()["probe_" + sys.argv[2]]()
    else:
        main()
