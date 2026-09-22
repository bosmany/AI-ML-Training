# 04 - Charged twice

**Category:** application  |  **Difficulty:** 3/5  |  **Target time:** 30-45 min

## Symptoms

- Support is getting tickets from customers charged twice for one order. It clusters on days when the
  payment processor is slow.
- In the ledger the two rows have different charge ids, seconds apart, with identical customer, amount and order.
- Server logs show no errors. Both requests were valid and both returned success (or one timed out at the client).
- The checkout client retries on timeouts by design, and the platform team confirms it re-sends the same
  request each time. Turning retries off "fixed" it in staging but failed real orders in production.
- `python app/demo.py` reproduces it in a few lines: one order, two ledger rows.

## What you have

- `app/` - the payment service (`payments.py`), the checkout client (`client.py`), the documented API
  contract (`API.md`), a demo (`demo.py`) and behaviour tests (`app/tests/`).
- `verify.py` - deterministic verifier (lost responses, replays, concurrent duplicates, restarts).

## Your job

1. Find the root cause (not just "duplicates happen").
2. Fix it in `app/` so it matches `app/API.md`, without breaking legitimate repeat purchases or the existing tests.
3. `python verify.py` must exit 0 (`BROKEN_TARGET=solution python verify.py` checks the reference).
4. Copy `postmortem_template.md` to `postmortem.md` and fill it in; add a prevention action
   (a test named `app/tests/test_regression_*.py` earns the +10).

Run with the course venv: `/home/laborant/repos/AI-ML-Training/.fastapi-venv/bin/python verify.py`
or `make broken ID=04` from the repo root. Scoring: see [`../README.md`](../README.md).
