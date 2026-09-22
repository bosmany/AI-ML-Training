#!/usr/bin/env python3
"""Verifier for 01-memory-leak.  Usage: python verify.py   (BROKEN_TARGET=solution to check the reference)"""
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_common"))
from harness import Verifier  # noqa: E402

N = 40000
HOT = 200
BUDGET_MB = 8.0
MIN_HOT_HIT = 0.80


def probe_soak():
    import gc
    import json
    import random
    import tracemalloc
    import service

    for i in range(50):                      # warm-up so imports/one-time state are not counted
        service.get_report("warm-up %d" % i)
    gc.collect()
    tracemalloc.start()
    base = tracemalloc.get_traced_memory()[0]
    rng = random.Random(7)
    hot_requests = hot_misses = 0
    for i in range(N):
        if rng.random() < 0.5:
            q, hot = "popular query %d" % rng.randrange(HOT), True
        else:
            q, hot = "  One-off search #%d  " % i, False
        before = service.STATS["computes"]
        service.get_report(q)
        if hot:
            hot_requests += 1
            if service.STATS["computes"] != before:
                hot_misses += 1
    gc.collect()
    growth = tracemalloc.get_traced_memory()[0] - base
    tracemalloc.stop()
    print(json.dumps({"growth_mb": growth / 1048576.0, "hot_requests": hot_requests, "hot_misses": hot_misses}))


def main():
    v = Verifier(__file__)
    data, err = v.probe(__file__, "soak", timeout=50)
    if data is None:
        v.check("soak completes", False, err)
    else:
        g = data["growth_mb"]
        v.check("memory stays flat under the soak (< %d MB retained)" % BUDGET_MB, g < BUDGET_MB, "retained %.1f MB" % g)
        hit = 1 - data["hot_misses"] / max(1, data["hot_requests"])
        v.check("popular queries still served from cache (>= %d%%)" % (MIN_HOT_HIT * 100), hit >= MIN_HOT_HIT, "hit ratio %.1f%%" % (hit * 100))
    v.pytest()
    v.finish()


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--probe":
        sys.path.insert(0, os.environ["BROKEN_TARGET_DIR"])
        globals()["probe_" + sys.argv[2]]()
    else:
        main()
