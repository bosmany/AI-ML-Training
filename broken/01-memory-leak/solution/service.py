"""Report worker: renders the dashboard tiles for a customer's search query.

Rendering is expensive (in production it fans out to three backends), so
results are cached, in a bounded LRU so memory cannot grow with traffic.
STATS['computes'] counts real renders; the tests and the load generator rely on it.
"""
import hashlib
import threading
from collections import OrderedDict

MAX_ENTRIES = 1000  # > the 200 popular queries, ~1.3 MB at ~1.3 KB per report

_CACHE = OrderedDict()
_LOCK = threading.Lock()
STATS = {"computes": 0}


def _normalise(query):
    return " ".join(query.lower().split())


def _render(query):
    """Pretend-expensive render. Returns a dict of about 1.3 KB."""
    STATS["computes"] += 1
    digest = hashlib.sha256(query.encode()).hexdigest()
    rows = [digest[i:i + 8] + "-" + str(i) for i in range(0, 64, 4)]
    return {"query": query, "digest": digest, "rows": rows}


def get_report(query):
    """Return the rendered report for a query (cached, LRU-bounded)."""
    key = _normalise(query)
    with _LOCK:
        report = _CACHE.get(key)
        if report is not None:
            _CACHE.move_to_end(key)
            return report
    report = _render(key)
    with _LOCK:
        _CACHE[key] = report
        _CACHE.move_to_end(key)
        while len(_CACHE) > MAX_ENTRIES:
            _CACHE.popitem(last=False)
    return report
