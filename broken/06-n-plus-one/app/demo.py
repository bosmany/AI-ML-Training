"""Time the report and count statements.   python demo.py [n_orders]   (2 ms simulated round trip per statement)"""
import os
import random
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db  # noqa: E402
import repo  # noqa: E402


def build(path, n_orders, seed=1):
    conn = db.connect(path)
    db.init_schema(conn)
    rng = random.Random(seed)
    conn.execute("INSERT INTO customers VALUES (1, 'Ada')")
    conn.executemany("INSERT INTO products VALUES (?,?,?)", [(i, "product-%d" % i, 100 + i * 7) for i in range(1, 41)])
    for o in range(1, n_orders + 1):
        conn.execute("INSERT INTO orders VALUES (?,?,?,?)", (o, 1, "2025-01-%02d" % (1 + o % 28), "paid"))
        for _ in range(rng.randint(0, 5)):
            conn.execute("INSERT INTO order_items (order_id, product_id, qty) VALUES (?,?,?)",
                         (o, rng.randint(1, 40), rng.randint(1, 4)))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "shop.db")
        build(path, n)
        conn = db.connect(path, latency_ms=2)
        count = []
        conn.set_trace_callback(lambda s: (count.append(s), time.sleep(0.002)))
        t = time.perf_counter()
        report = repo.orders_report(conn, 1)
        print("orders=%d statements=%d time=%.2fs" % (len(report["orders"]), len(count), time.perf_counter() - t))
