"""Report worker: renders the dashboard tiles for a customer's search query.

Rendering is expensive (in production it fans out to three backends), so
results are cached.  STATS['computes'] counts real renders; the tests and the
load generator rely on it.
"""
import hashlib

_CACHE = {}
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
    """Return the rendered report for a query (cached)."""
    key = _normalise(query)
    report = _CACHE.get(key)
    if report is None:
        report = _CACHE[key] = _render(key)
    return report
