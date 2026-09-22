# 01 - The worker that grows until it dies

**Category:** application  |  **Difficulty:** 2/5  |  **Target time:** 20-30 min

## Symptoms

- The report-rendering worker starts at roughly 60 MB. Under real traffic it climbs steadily and, after a
  few hours, the container is OOM-killed and restarted. Then the cycle repeats.
- Latency and CPU look healthy right up to the kill. No errors are logged.
- The climb is faster on days with more distinct users, not on days with more requests.
- Raising the container limit only moved the kill later. Restarting on a schedule was tried as a stopgap.

## What you have

- `app/` - the worker (`service.py`), a soak tool (`python app/loadgen.py` prints RSS every 5,000 requests),
  the operating targets (`app/SLO.md`) and behaviour tests (`app/tests/`).
- `verify.py` - deterministic verifier (tracemalloc soak, no wall-clock timing).

## Your job

1. Find the root cause (not just "memory goes up").
2. Fix it in `app/` while keeping the targets in `app/SLO.md` and the existing tests green.
3. `python verify.py` must exit 0 (`BROKEN_TARGET=solution python verify.py` checks the reference).
4. Copy `postmortem_template.md` to `postmortem.md` and fill it in; add a prevention action
   (a test named `app/tests/test_regression_*.py` earns the +10).

Run with the course venv: `/home/laborant/repos/AI-ML-Training/.fastapi-venv/bin/python verify.py`
or `make broken ID=01` from the repo root. Scoring: see [`../README.md`](../README.md).
