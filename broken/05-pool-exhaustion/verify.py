#!/usr/bin/env python3
"""Verifier for 05-pool-exhaustion.  Usage: python verify.py   (BROKEN_TARGET=solution to check the reference)"""
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_common"))
from harness import Verifier  # noqa: E402


def probe_paths():
    import json
    import random
    import tempfile
    import threading
    from db import ConnectionPool, PoolTimeout, init_db
    from service import NotFound, OrderService, ValidationError

    import atexit
    import shutil
    d = tempfile.mkdtemp()
    atexit.register(shutil.rmtree, d, True)
    path = os.path.join(d, "shop.db")
    init_db(path)
    pool = ConnectionPool(path, size=10, timeout=0.15)    # roomy: lets us count every leak without timing out
    svc = OrderService(pool)
    out = {}

    ids = [svc.create_order("cust%d" % (i % 5), 1000 + i) for i in range(12)]
    with pool.connection() as c:
        c.execute("UPDATE orders SET status='shipped' WHERE id IN (%s)" % ",".join(str(i) for i in ids[:4]))
        c.commit()
    shipped, open_ids = ids[:4], ids[4:]

    def call(fn, *args):
        try:
            return "ok", fn(*args)
        except NotFound:
            return "NotFound", None
        except ValidationError:
            return "ValidationError", None
        except PoolTimeout:
            return "PoolTimeout", None

    # sequential: what does each kind of request leave behind?
    kinds = {
        "get_found": (svc.get_order, open_ids[0]),
        "get_missing": (svc.get_order, 987654),
        "create_ok": (svc.create_order, "zed", 700),
        "create_invalid": (svc.create_order, "", 700),
        "cancel_ok": (svc.cancel_order, open_ids[1]),
        "cancel_shipped": (svc.cancel_order, shipped[0]),
        "cancel_missing": (svc.cancel_order, 987654),
        "list": (svc.list_orders, "cust1"),
    }
    leaks, outcomes, before = {}, {}, 0
    for name, (fn, *args) in kinds.items():
        outcomes[name], _ = call(fn, *args)
        leaks[name] = pool.in_use - before
        before = pool.in_use
    out["leaks"] = leaks
    out["outcomes"] = outcomes
    if any(leaks.values()):
        print(json.dumps(out))
        return

    # fresh, deliberately small pool for the rest
    pool = ConnectionPool(path, size=4, timeout=0.15)
    svc = OrderService(pool)

    # behaviour is preserved (errors still reach the caller, values unchanged)
    out["behaviour"] = [
        outcomes == {"get_found": "ok", "get_missing": "NotFound", "create_ok": "ok", "create_invalid": "ValidationError",
                     "cancel_ok": "ok", "cancel_shipped": "ok", "cancel_missing": "NotFound", "list": "ok"},
        svc.cancel_order(shipped[1]) is False,
        svc.cancel_order(open_ids[2]) is True,
        svc.get_order(open_ids[2])["status"] == "cancelled",
    ]

    # concurrent mix of every path against the small pool
    stats = {"PoolTimeout": 0, "total": 0}
    lock = threading.Lock()

    def worker(seed):
        rng = random.Random(seed)
        for _ in range(25):
            r = rng.random()
            if r < 0.3:
                res, _ = call(svc.get_order, 987654)
            elif r < 0.5:
                res, _ = call(svc.create_order, "", 5)
            elif r < 0.7:
                res, _ = call(svc.cancel_order, rng.choice(shipped))
            elif r < 0.85:
                res, _ = call(svc.get_order, rng.choice(open_ids))
            else:
                res, _ = call(svc.create_order, "cust9", 250)
            with lock:
                stats["total"] += 1
                stats["PoolTimeout"] += res == "PoolTimeout"

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    out["concurrent"] = {"timeouts": stats["PoolTimeout"], "total": stats["total"], "in_use_after": pool.in_use}
    print(json.dumps(out))


def main():
    v = Verifier(__file__)
    o, err = v.probe(__file__, "paths", timeout=40)
    if o is None:
        v.check("scenarios run", False, err)
    else:
        leaked = {k: n for k, n in o["leaks"].items() if n}
        v.check("every request type returns its connection to the pool", not leaked,
                "leaks after: %s" % (", ".join(leaked) or "none"))
        if "behaviour" in o:
            v.check("errors still propagate and results are unchanged (nothing swallowed)", all(o["behaviour"]), str(o["behaviour"]))
            c = o["concurrent"]
            v.check("no pool timeouts under concurrent load (pool of 4, 6 threads)", c["timeouts"] == 0,
                    "%d of %d requests timed out" % (c["timeouts"], c["total"]))
            v.check("pool fully available after the load", c["in_use_after"] == 0, "in use: %d" % c["in_use_after"])
        else:
            v.check("errors still propagate and results are unchanged (nothing swallowed)", False, "skipped: leaks found first")
            v.check("no pool timeouts under concurrent load (pool of 4, 6 threads)", False, "skipped: leaks found first")
    v.pytest()
    v.finish()


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--probe":
        sys.path.insert(0, os.environ["BROKEN_TARGET_DIR"])
        globals()["probe_" + sys.argv[2]]()
    else:
        main()
