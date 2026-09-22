# 12 - Writes stall while the batch runs

**Category:** databases  |  **Difficulty:** medium  |  **Target time:** 20-30 min

## Symptoms

- Every few minutes the web tier logs bursts of `sqlite3.OperationalError: database is locked` from
  `record_event()`, and requests that normally take 3 ms take exactly 5 seconds and then fail.
- The bursts line up with the batch worker (`process_pending`) running. The longer the batch, the longer
  the burst; with 200 queued jobs the site was effectively read-only for several minutes.
- The worker itself is healthy: CPU is idle, the jobs all finish, results are correct.
- The database file is small and the disk is fine. Raising the timeout made requests hang longer instead
  of failing sooner; switching the journal mode did not change the outcome.

## What you have

- `app/queue_worker.py` - queue + event log on SQLite; `python app/demo.py` reproduces the error in ~2 s.
- `verify.py` - deterministic verifier (no sleeps, no thread races).

## Your job

1. Find the root cause.
2. Fix it in `app/`, keeping behaviour: every job is processed once with the right result; a job whose
   `enrich()` raises is marked `failed` with the error text and does not stop the others.
3. `python verify.py` must exit 0 (`BROKEN_TARGET=solution python verify.py` checks the reference).
4. Fill in `postmortem_template.md` and add a prevention action.

Run with the course venv: `/home/laborant/repos/AI-ML-Training/.fastapi-venv/bin/python verify.py`
