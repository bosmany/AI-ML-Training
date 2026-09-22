# 11 - The order page that takes 30 seconds

**Category:** databases  |  **Difficulty:** easy  |  **Target time:** 15-25 min

## Symptoms

- The customer "My orders" page (`recent_orders` + `customer_summary`) took under 100 ms at launch.
  Two years later production p95 for it is around 30 seconds, and the database CPU is pinned whenever
  the page is busy.
- The slowness follows the size of the `orders` table, not the traffic: every customer is equally slow,
  including a customer with only 25 orders.
- Restarting the app or the database changes nothing. Adding hardware helped for a month.
- On a laptop the 150,000-row sample in `app/seed.py` answers in a few milliseconds, so wall-clock time
  alone does not show the problem locally. Something else does.

## What you have

- `app/` - the service code (SQLite). `python app/bench.py` builds a sample database in a temp dir.
- `verify.py` - deterministic verifier (no wall-clock timing).

## Your job

1. Find the root cause (not just "it is slow").
2. Fix it in `app/` without changing what the queries return.
3. `python verify.py` must exit 0 (`BROKEN_TARGET=solution python verify.py` checks the reference).
4. Fill in `postmortem_template.md` and add a prevention action (a test or check that would have caught it).

Run with the course venv: `/home/laborant/repos/AI-ML-Training/.fastapi-venv/bin/python verify.py`
