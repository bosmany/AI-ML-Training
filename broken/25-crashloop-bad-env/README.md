# 25 - The service that never stays up

**Category:** containers  |  **Difficulty:** easy  |  **Target time:** 10-20 min

## Symptoms

- After the latest deploy the `web` service never becomes available. `docker compose ps` alternates between
  `Restarting` and `Up less than a second`, and the restart counter keeps climbing (the container-world twin of
  Kubernetes `CrashLoopBackOff`).
- The healthcheck reports `unhealthy` (or `starting` forever). Nothing answers on the service port.
- Yesterday's image, the same image tag and the same code worked. The only change in the deploy was configuration.
- The team's first reaction was to raise the restart limit and add a longer startup delay; the loop continued.

## What you have

- `app/docker-compose.yml` and `app/service/` (Python 3.12 on alpine).
- `verify.py` - starts your compose file under a private project name, judges via `docker inspect` / logs and always
  tears everything down. Needs docker (no sudo) and the image present locally: `docker pull python:3.12-alpine`.
- Try it yourself: `cd app && docker compose up -d`, and clean up with `docker compose down -v`.

## Your job

1. Find the root cause.
2. Fix it in `app/`. Keep supervision (restart policy) and the service's fail-fast validation.
3. `python verify.py` must exit 0 (`BROKEN_TARGET=solution python verify.py` checks the reference).
4. Fill in `postmortem_template.md` and add a prevention action.

Run with the course venv: `/home/laborant/repos/AI-ML-Training/.fastapi-venv/bin/python verify.py`
