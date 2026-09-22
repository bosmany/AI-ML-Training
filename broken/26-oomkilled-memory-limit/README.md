# 26 - Exit code 137

**Category:** containers  |  **Difficulty:** easy-medium  |  **Target time:** 15-25 min

## Symptoms

- The nightly report container stops after a few seconds with exit code 137 and no error message or stack trace in
  its logs; the last output line never appears. `docker compose ps -a` shows it as `Exited (137)`.
- It works on a developer laptop (where nothing limits memory) and in unit tests with a small sample.
- Rerunning gives the same result every time, at roughly the same point. The host has plenty of free memory.
- The team's first reaction was `restart: always`; that only made it die repeatedly.

## What you have

- `app/docker-compose.yml` and `app/job/report.py` (Python 3.12 on alpine).
- `verify.py` - runs your compose file under a private project name, judges via `docker inspect` and the job's
  output, always cleans up. Needs docker (no sudo) and the image locally: `docker pull python:3.12-alpine`.
- Try it yourself: `cd app && docker compose up -d && docker compose ps -a`; clean up with `docker compose down -v`.

## Your job

1. Find the root cause.
2. Fix it in `app/` while keeping a memory limit (the platform team requires one) and the job's output identical.
3. `python verify.py` must exit 0 (`BROKEN_TARGET=solution python verify.py` checks the reference).
4. Fill in `postmortem_template.md` and add a prevention action.

Run with the course venv: `/home/laborant/repos/AI-ML-Training/.fastapi-venv/bin/python verify.py`
