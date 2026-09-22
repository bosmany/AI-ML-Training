# 05 - Fine at first, then everything times out

**Category:** application  |  **Difficulty:** 3/5  |  **Target time:** 25-40 min

## Symptoms

- About ten minutes into normal traffic the API begins returning 500s with the message
  "timed out waiting for a database connection". Then almost every request fails.
- The database is nearly idle at that point: no slow queries, no locks, low CPU.
- A restart fixes it completely, until it happens again. On busy days it comes back sooner.
- Raising the pool size from 5 to 20 postponed the first failure but did not remove it.
- `python app/loadtest.py` reproduces it in a few seconds and prints the pool state at the end.

## What you have

- `app/` - a small blocking connection pool (`db.py`), the order service (`service.py`), a load test
  and behaviour tests (`app/tests/`).
- `verify.py` - deterministic verifier (per-request-type pool accounting, concurrent load on a pool of 4).

## Your job

1. Find the root cause (not just "the pool is too small").
2. Fix it in `app/` without changing how errors are reported to callers.
3. `python verify.py` must exit 0 (`BROKEN_TARGET=solution python verify.py` checks the reference).
4. Copy `postmortem_template.md` to `postmortem.md` and fill it in; add a prevention action
   (a test named `app/tests/test_regression_*.py` earns the +10).

Run with the course venv: `/home/laborant/repos/AI-ML-Training/.fastapi-venv/bin/python verify.py`
or `make broken ID=05` from the repo root. Scoring: see [`../README.md`](../README.md).
