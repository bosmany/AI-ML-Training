"""Hammer the service with a realistic mix and print pool state.   python loadtest.py"""
import os
import random
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import ConnectionPool, PoolTimeout, init_db  # noqa: E402
from service import NotFound, OrderService, ValidationError  # noqa: E402


def main():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "shop.db")
        init_db(path)
        pool = ConnectionPool(path, size=4, timeout=0.15)
        svc = OrderService(pool)
        ids = [svc.create_order("cust%d" % (i % 5), 1000 + i) for i in range(20)]
        stats = {"ok": 0, "not_found": 0, "invalid": 0, "pool_timeout": 0}

        def worker(seed):
            rng = random.Random(seed)
            for _ in range(25):
                try:
                    r = rng.random()
                    if r < 0.4:
                        svc.get_order(rng.choice(ids) if rng.random() < .5 else 99999)
                    elif r < 0.6:
                        svc.create_order("" if rng.random() < .5 else "cust1", 500)
                    else:
                        svc.cancel_order(rng.choice(ids))
                    stats["ok"] += 1
                except NotFound:
                    stats["not_found"] += 1
                except ValidationError:
                    stats["invalid"] += 1
                except PoolTimeout:
                    stats["pool_timeout"] += 1

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        print(stats, "in_use at end:", pool.in_use, "of", pool.size)


if __name__ == "__main__":
    main()
