"""Soak the worker and print its resident memory as it runs.

    python loadgen.py            # 40,000 requests, RSS every 5,000
    python loadgen.py 100000
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import service  # noqa: E402


def rss_mb():
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024.0
    return float("nan")


def workload(n, seed=7, hot=200):
    """Half the traffic re-asks one of `hot` popular queries, half is one-off searches."""
    rng = random.Random(seed)
    for i in range(n):
        if rng.random() < 0.5:
            yield "popular query %d" % rng.randrange(hot), True
        else:
            yield "  One-off search #%d  " % i, False


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40000
    print("requests    rss_mb   renders")
    for i, (q, _hot) in enumerate(workload(n), 1):
        service.get_report(q)
        if i % 5000 == 0:
            print("%8d  %8.1f  %8d" % (i, rss_mb(), service.STATS["computes"]))


if __name__ == "__main__":
    main()
