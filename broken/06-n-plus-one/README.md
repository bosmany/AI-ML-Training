# 06 - The slow orders endpoint

**Category:** application  |  **Difficulty:** 2/5  |  **Target time:** 20-30 min

## Symptoms

- `GET /reports/orders` takes about 4 seconds for a customer with 300 orders and 40 ms for one with 3.
  Response time follows the size of the customer, not the traffic.
- Database CPU is low and there are no slow queries in the slow-query log: every individual query is fast.
- The database's general query log for one request is thousands of lines long.
- Adding application servers did not help; moving the database closer (lower latency) helped a little.
- `python app/demo.py 300` shows the numbers (with a simulated 2 ms round trip per statement).

## What you have

- `app/` - the data access layer (`repo.py`), schema helpers (`db.py`), a demo and behaviour tests (`app/tests/`).
- `verify.py` - deterministic verifier (counts statements; it does not use wall-clock time).

## Your job

1. Find the root cause (not just "the endpoint is slow").
2. Fix it in `app/` without changing the report's content or ordering.
3. `python verify.py` must exit 0 (`BROKEN_TARGET=solution python verify.py` checks the reference).
4. Copy `postmortem_template.md` to `postmortem.md` and fill it in; add a prevention action
   (a test named `app/tests/test_regression_*.py` earns the +10).

Run with the course venv: `/home/laborant/repos/AI-ML-Training/.fastapi-venv/bin/python verify.py`
or `make broken ID=06` from the repo root. Scoring: see [`../README.md`](../README.md).
