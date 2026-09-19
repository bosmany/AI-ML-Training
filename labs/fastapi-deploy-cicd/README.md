# Lab: Ship it - Dockerfile, Compose and GitHub Actions for a FastAPI service

You get a tiny FastAPI service (`GET /health`). Your job is everything that gets it to production:
a hardened `Dockerfile`, a `.dockerignore`, a `docker-compose.yml` and a CI workflow. A set of
**static policy tests** (PyYAML + regex, no Docker needed) checks the files against the rules real
platform teams enforce in code review.

## Why it matters in a real job

A model that only runs in your notebook is not shipped. "Containerise it, run it locally with its
database, and add CI" is the standard first-week task on an ML-platform or backend team, and the
mistakes this lab pins are the ones that reach production: `:latest` base images, containers running as
root, secrets baked into layers, `depends_on` that does not wait for the database to be ready, CI that
builds an image before the tests pass, and third-party actions pinned to a moving `@main`.

## Prerequisites (course chapters)

- [FastAPI capstone and deployment](../../fastapi/ch41-fastapi-capstone-deployment.html)
- [Cloud and container ops](../../devops/do04-cloud-and-container-ops.html)
- [Automation scripts and resilience](../../devops/do03-automation-scripts-resilience.html)
- [Model deployment](../../mlops/ch31-model-deployment.html)

## Run it

```bash
cd labs/fastapi-deploy-cicd
pip install -r requirements.txt          # pyyaml + pytest only
pytest -q                                # starter: everything fails until you write the files
LAB_TARGET=solution pytest -q            # maintainers / CI: the reference passes
(cd starter && python -m lab)            # friendlier report of every rule, with the reason
```

You edit **the files under `starter/assets/`**, not the Python package. `starter/lab/` contains the loaders
and linter the tests use (read `lab/lint.py` to see exactly what each rule checks). The tests import
`from lab import ...` and choose `starter/` or `solution/` from `LAB_TARGET`.

## Files

```
starter/assets/
  app/main.py, requirements.txt, requirements-dev.txt, tests/health_check.py   provided (the service + its own tests)
  Dockerfile                        YOU WRITE (task 1)
  .dockerignore                     YOU WRITE (task 2)
  docker-compose.yml                YOU WRITE (task 3)
  .github/workflows/ci.yml          YOU WRITE (task 4)
```

`starter/assets/` is the Docker build context and, conceptually, the root of your repository (that is
why the workflow uses paths like `requirements.txt` and `tests/health_check.py`).

## Tasks

1. **Dockerfile** - multi-stage (builder installs dependencies, runtime copies them with `COPY --from`);
   base image pinned to a version tag (no `:latest`, no untagged); `requirements.txt` copied and installed
   *before* the source; `pip install --no-cache-dir`; non-root `USER`; `HEALTHCHECK` on `/health` with
   explicit `--interval`/`--timeout`; `ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1`; `EXPOSE 8000`;
   exec-form `CMD` running `uvicorn ... --host 0.0.0.0`; no secrets baked in.
2. **.dockerignore** - exclude `.git`, `.env` and `.env.*`, virtualenvs, `__pycache__`/`*.pyc`, caches;
   do not exclude what the build needs (`requirements.txt`, `app/`).
3. **docker-compose.yml** - services `db` (pinned postgres) and `api` (built from `.`): healthchecks on
   both, `api.depends_on.db.condition: service_healthy`, the DB password and `DATABASE_URL` built from
   `${POSTGRES_PASSWORD}` (required, no default), port published as `"${API_PORT:-8000}:8000"`, restart policies.
4. **.github/workflows/ci.yml** - trigger on `push` (main) and `pull_request`; top-level
   `permissions: contents: read`; a `test` job (checkout, `actions/setup-python` with `cache: pip` and the
   *same* Python version as your image, install, `pytest tests/health_check.py`); a `build` job with
   `needs: test` that builds the image and only pushes when the event is not a pull request (the one job that
   needs `packages: write` declares it itself); every action pinned to a version tag or SHA; `timeout-minutes`
   on every job; credentials only via `${{ secrets.* }}`.

## Hints

<details><summary>Why copy requirements.txt first?</summary>

Docker caches each layer and invalidates it when its inputs change. If you `COPY . .` before
`pip install`, editing one line of code re-downloads every dependency. Copy only `requirements.txt`, install,
then copy the source.
</details>

<details><summary>My HEALTHCHECK fails: curl not found</summary>

`python:*-slim` has no curl. Use Python itself:
`CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]`
</details>

<details><summary>How do I get the venv/pip out of the final image?</summary>

`pip install --prefix=/install -r requirements.txt` in the builder, then `COPY --from=builder /install /usr/local` in the runtime stage.
</details>

<details><summary>Why is `on:` a boolean in my parsed workflow?</summary>

YAML 1.1 (PyYAML) turns the bare key `on` into `True`. `lab/workflow.py` converts it back; remember this
whenever you parse Actions files in Python.
</details>

<details><summary>What is the compose syntax for "wait until healthy"?</summary>

```yaml
depends_on:
  db:
    condition: service_healthy
```
The short list form (`depends_on: [db]`) only waits for the container to *start*.
</details>

## Optional: try it for real

The tests never need Docker. If you have Docker installed you can verify your files for real:

```bash
cd starter/assets
docker build -t candidate-api:dev .
docker run --rm -p 8000:8000 candidate-api:dev          # curl localhost:8000/health
POSTGRES_PASSWORD=change-me API_PORT=8000 docker compose up --build --wait
docker compose ps                                       # both services "healthy"
POSTGRES_PASSWORD=change-me docker compose down -v
```

(The reference solution in `solution/assets/` was verified this way: image builds, runs as uid 10001, reports
`healthy`; compose brings both services up healthy.)

## Stretch goals

- Add `hadolint` and `actionlint` to the workflow and fix what they report.
- Use BuildKit cache mounts (`RUN --mount=type=cache,target=/root/.cache/pip`).
- Pin base images by digest and add Dependabot for both `docker` and `github-actions` ecosystems.
- Add a `docker compose` override file for local development with hot reload.
- Scan the image with Trivy in CI and fail on HIGH/CRITICAL findings.

## How this comes up in interviews

- "Walk me through a production Dockerfile for a Python service." (multi-stage, pinned tag, non-root, healthcheck, cache order, exec form.)
- "Why not `latest`? Why not run as root? Why exec-form CMD?"
- "`depends_on` did not wait for Postgres - why?" (started vs healthy.)
- "How would you stop a fork's pull request from stealing your secrets / pushing an image?" (`permissions`,
  no `pull_request_target`, `push` only when not a PR.)
- "Why pin actions by SHA?" (supply-chain attacks on moving tags.)
