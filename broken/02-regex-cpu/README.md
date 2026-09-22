# 02 - One request pins the CPU

**Category:** application  |  **Difficulty:** 3/5  |  **Target time:** 25-40 min

## Symptoms

- Every few days one API worker sits at 100% CPU and stops answering. Health checks fail and the pod is
  restarted. Then it happens again a few days later.
- The last log line before each incident is a signup or tagging request with an unusually long,
  odd-looking string. Other requests around it are ordinary and fast.
- Memory, disk and the database are all normal. Adding replicas only gave the problem more workers to take down.
- `python app/bench.py username 20` finishes instantly. Try 24, then 26, then think before you try 40.

## What you have

- `app/` - the validators (`validators.py`), a timing helper (`bench.py`) and behaviour tests (`app/tests/`).
- `verify.py` - deterministic verifier (per-input alarm timers, CPU accounting, differential test).

## Your job

1. Find the root cause (not just "the regex is slow").
2. Fix it in `app/` without changing which strings are accepted or rejected.
3. `python verify.py` must exit 0 (`BROKEN_TARGET=solution python verify.py` checks the reference).
4. Copy `postmortem_template.md` to `postmortem.md` and fill it in; add a prevention action
   (a test named `app/tests/test_regression_*.py` earns the +10).

Run with the course venv: `/home/laborant/repos/AI-ML-Training/.fastapi-venv/bin/python verify.py`
or `make broken ID=02` from the repo root. Scoring: see [`../README.md`](../README.md).
