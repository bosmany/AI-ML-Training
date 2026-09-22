# Lab: Real container deploy (FastAPI model server + Docker + Kubernetes manifests)

Ship a real scikit-learn model behind FastAPI inside a **real** Docker container - the actual
`docker build` / `docker run`, not a mock. You write the `/predict` route, then fix a Dockerfile that
"works" but a platform-team review would reject: a single floating-tag stage, root user, no
healthcheck, a secret baked into `ENV`, source copied before dependencies, no `--no-cache-dir`, shell-form
`CMD`, and uvicorn left bound to its unreachable `127.0.0.1` default. The automated tests really build
the image, really run the container, really `curl` its `/health` and `/predict` endpoints, really check
who the process runs as, and really tear the container and image down afterwards.

This lab stands on its own: it ships a complete model-serving app (iris classifier) so it does not
depend on any other lab being present.

## Why it matters in a real job

Anyone can get `pytest` green against code running on their own laptop's Python. Shipping it means
someone else's machine, with none of your installed packages, running as a stranger's `root` by
default unless you say otherwise, with a orchestrator that needs to know when the process is actually
ready. This lab is the difference between "it runs on my machine" and "here's the image, here's the
manifest, here's how we roll it back."

## Prerequisites (course chapters)

- [FastAPI ch. 41: capstone and deployment](../../fastapi/ch41-fastapi-capstone-deployment.html)
- [Systems 4: Linux, Docker, Kubernetes](../../systems/sf04-linux-docker-kubernetes.html)
- [MLOps ch. 32: MLOps fundamentals capstone](../../mlops/ch32-mlops-fundamentals-capstone.html)

## What's graded automatically vs. what needs Docker on your machine

**Everything in `tests/` is graded automatically, for real - there is no offline/hermetic half.** It
needs nothing but a local Docker daemon (no API key, no cloud account, no `kind`/Kubernetes).

```bash
cd labs/mlops-real-container-deploy
pip install -r requirements.txt          # pytest, httpx - the Dockerfile lint checks need nothing else
pytest -q                                # starter: 10 lint failures + 5 live-container errors
LAB_TARGET=solution pytest -q            # maintainers / CI: reference solution passes, real Docker required
```

`tests/test_dockerfile_lint.py` runs in milliseconds (pure text parsing, no Docker). `tests/test_live_container.py`
takes ~10-50s: it really runs `docker build`, `docker run -p <free-port>:8000`, polls real HTTP, then
always stops the container and removes the image in a `finally` - even if a test fails, times out, or
Ctrl-C interrupts the run. It needs Docker (no sudo required) and network access to pull
`python:3.12-slim-bookworm` the first time (cached after that, ~190MB).

The `k8s/` manifests and `scripts/kind_demo.sh` are a **separate, manual-only** reference track - see
below. They are not part of the pytest-graded contract because creating a real `kind` cluster needs
privileges (nested containers/cgroups/iptables) a sandboxed grading environment does not grant.

Edit `starter/assets/app/main.py` (the `/predict` route) and `starter/assets/Dockerfile`. Everything
else in `starter/` (`model.py`, `schemas.py`, `train_model.py`, `requirements.txt`) is provided.

## The stack

```
starter/assets/app/main.py     # TODO: implement the /predict route (task 1)
starter/assets/Dockerfile      # TODO: fix 10 real production issues (task 2)
starter/assets/app/model.py, schemas.py, train_model.py   # provided - do not edit
solution/assets/...            # reference implementation of both tasks
solution/lab/lint.py           # the static Dockerfile policy checks (read this to see every rule)
solution/lab/dockerfile.py     # small dependency-free Dockerfile parser the lint checks run on
tests/test_dockerfile_lint.py  # 10 hermetic tests, no Docker needed, run in milliseconds
tests/test_live_container.py  # 5 tests against a REAL docker build + docker run
tests/conftest.py             # the live_server session fixture: build, run, wait, always clean up
k8s/deployment.yaml, service.yaml   # reference manifests (manual track, not graded)
scripts/kind_demo.sh           # reference kind cluster demo: rollout, rollback (manual track, not graded)
```

### The app (`app/main.py`, `app/model.py`, `app/schemas.py`)

| Endpoint | Behaviour |
| --- | --- |
| `GET /health` | `{"status": "ok", "model_loaded": true/false}` |
| `POST /predict` `{"sepal_length", "sepal_width", "petal_length", "petal_width"}` (all `float`, `cm`) | real `LogisticRegression` trained on the iris dataset, baked into the image at build time |

`model.py` trains the classifier **inside the Docker builder stage**, on the copy of the iris dataset
that ships inside scikit-learn itself (no network access needed to build the image), and pickles it
with `joblib`. Only that artifact - never scikit-learn's dataset or the training script - is copied
into the runtime stage. `load_model()` returns `None` instead of raising if the artifact is missing, so
`/health` can report `"model_loaded": false` instead of the process crashing at import time.

## Tasks

1. **`app/main.py` - the `/predict` route.** If `_model` is `None`, raise `HTTPException(503, ...)`
   instead of crashing. Build the feature row in the exact order `app.model.FEATURE_NAMES` documents
   (scikit-learn cares about column order, not names). Call `.predict(...)` and `.predict_proba(...)`,
   map the predicted index to its class name via `target_names`, and return a `PredictResponse` keyed
   by class name.
2. **`assets/Dockerfile` - fix all 10 issues**, each backed by its own `lint.py` check and named test:
   1. **Multi-stage build**: separate a `builder` stage (trains the model) from a slim runtime stage
      that only ships the artifact and the app - `check_multi_stage`.
   2. **Pin every base image** to an exact version tag (`python:3.12-slim-bookworm`, not `python:3-slim`
      or `:latest`) - `check_pinned_base_images`.
   3. **Non-root `USER`** in the final stage - `check_non_root_user`.
   4. **A real `HEALTHCHECK`** that calls `/health`, with explicit `--interval`/`--timeout` -
      `check_healthcheck`.
   5. **No secrets baked into `ENV`/`ARG`** - `check_no_baked_secrets`.
   6. **`requirements.txt` copied and installed before the rest of the source**, so editing app code
      does not invalidate the dependency-install layer cache - `check_cache_friendly_layer_order`.
   7. **`pip install --no-cache-dir`** (or `ENV PIP_NO_CACHE_DIR=1`) - `check_pip_no_cache`.
   8. **Exec-form `CMD`** (a JSON array), so uvicorn is PID 1 and actually receives `SIGTERM` on
      `docker stop` instead of a shell swallowing it - `check_exec_form_command`.
   9. **`ENV PYTHONUNBUFFERED=1` and `PYTHONDONTWRITEBYTECODE=1`** - `check_python_runtime_env`.
   10. **`EXPOSE` the port and bind uvicorn to `0.0.0.0`** (not its `127.0.0.1` default) so the
       container is reachable from outside itself via `docker run -p` - `check_exposed_port_and_bind_address`.

The starter Dockerfile's own top-of-file comment lists these same 10 rules - read it first.

## Hints

<details><summary>Why does the starter fail ALL 5 live-container tests, not just the ones about the specific bug?</summary>

`tests/conftest.py`'s `live_server` fixture builds the image once per session and waits up to 45s for
`/health` to answer over real HTTP through the mapped port. If uvicorn is still bound to `127.0.0.1`
(rule 10), the container never becomes reachable from the host - `docker run -p host:container` maps
onto the container's external interface, not its loopback - so the wait always times out and every test
that depends on `live_server` fails together. Fixing rule 10 alone will get you past the timeout; the
tests then start telling you about whatever else is still wrong (non-root user, healthcheck, ...).
</details>

<details><summary>Multi-stage build: what exactly has to reference the earlier stage?</summary>

`check_multi_stage` does not just count `FROM` lines - it also requires the final stage to actually
`COPY --from=<builder-alias-or-index> ...` something out of the earlier stage. Two `FROM`s where the
second one ignores the first and starts over is not a multi-stage build in any way that matters; the
runtime stage must not carry `pip`'s build tools, only the trained artifact and installed packages
(`COPY --from=builder /usr/local/lib/.../site-packages`, `COPY --from=builder /build/model ./model`).
</details>

<details><summary>Why check both `docker top` AND `docker exec ... id -u` for non-root?</summary>

`test_container_process_does_not_run_as_root` checks both because they catch different mistakes:
`docker top` reports the UID of the actual running PID 1 process (so a `USER app` instruction that is
overridden by a later `RUN` back to root, or a shell-form `CMD` that re-execs as root, would still show
up here); `docker exec ... id -u` confirms the image's configured default user - the one anyone
`docker exec`-ing in to debug would land as - is also non-root. A Dockerfile could pass one check and
fail the other if `USER` were set correctly but something at runtime dropped back to root.
</details>

## Kubernetes (reference, manual - not graded)

`k8s/deployment.yaml` and `k8s/service.yaml` are a complete, correct manifest pair for a human with
`kind`/`kubectl` on a real machine: 3 replicas, `RollingUpdate` with `maxSurge: 1, maxUnavailable: 0`,
readiness/liveness probes against `/health`, resource requests/limits, and a `securityContext` that
mirrors the Dockerfile's own hardening (`runAsNonRoot`, `readOnlyRootFilesystem`, all capabilities
dropped). `scripts/kind_demo.sh` is a runnable, end-to-end demo script: create a `kind` cluster, build
**two** real images from `solution/assets` (v1 as-is, v2 with one changed line so the rollout is a real
different container, not a no-op), load both straight into the cluster's node, apply the manifests,
verify v1 answers through the Service, do a real rolling update to v2, then a real rollback to v1 -
confirmed each time via `kubectl rollout status`/`history` and a real `curl` through `kubectl
port-forward`.

```bash
bash scripts/kind_demo.sh    # needs docker + kind + kubectl on a real machine; not run by pytest
```

## Real output captured from an actual run (2026-09-22)

Everything below is pasted from an actual `docker build` / `docker run` / `curl` / `pytest` session
against this lab's `solution/` code.

**Building and running the real image:**

```
$ docker build -t mlops-real-container-deploy:solution solution/assets
...
#20 naming to docker.io/library/mlops-real-container-deploy:solution done

$ docker run -d --rm -p 18001:8000 mlops-real-container-deploy:solution
f8b7cfb6baa5...
$ docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
NAMES         STATUS                            PORTS
readme-demo   Up 2 seconds (health: starting)   0.0.0.0:18001->8000/tcp
```

**Real predictions from the real trained model:**

```
$ curl -s http://127.0.0.1:18001/health
{"status":"ok","model_loaded":true}

$ curl -s -X POST http://127.0.0.1:18001/predict -H 'Content-Type: application/json' \
    -d '{"sepal_length":5.1,"sepal_width":3.5,"petal_length":1.4,"petal_width":0.2}'
{"predicted_class":"setosa","predicted_class_index":0,"probabilities":{"setosa":0.9816568294440160,"versicolor":0.0183431561609386,"virginica":1.4395045350105303e-08}}

$ curl -s -X POST http://127.0.0.1:18001/predict -H 'Content-Type: application/json' \
    -d '{"sepal_length":6.5,"sepal_width":3.0,"petal_length":5.2,"petal_width":2.0}'
{"predicted_class":"virginica","predicted_class_index":2,"probabilities":{"setosa":0.0001369637895850,"versicolor":0.1572306829530165,"virginica":0.8426323532573984}}

$ curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:18001/predict -d '{"sepal_length":5.1}'
422
```

**Real non-root check and real healthcheck transition:**

```
$ docker exec readme-demo id -u
10001

$ docker inspect --format '{{.State.Health.Status}}' readme-demo
healthy
```

**Full automated pytest run against `starter/` (before any fix - everything fails together):**

```
$ pytest -q
10 failed, 5 errors in 51.76s
```

10 real Dockerfile-lint failures (multi-stage, pinned base image, non-root user, healthcheck, secrets,
layer order, `--no-cache-dir`, exec-form CMD, `PYTHONUNBUFFERED`/`PYTHONDONTWRITEBYTECODE`, `EXPOSE`
+ `0.0.0.0`), and all 5 live-container tests error because the starter's uvicorn never becomes
reachable through the mapped port (rule 10 - `127.0.0.1` binding).

**Full automated pytest run against `solution/` (real Docker, real container, real teardown), run 3
times in a row for determinism:**

```
$ LAB_TARGET=solution pytest -q
...............                                                          [100%]
15 passed in 9.72s
$ LAB_TARGET=solution pytest -q
...............                                                          [100%]
15 passed in 10.15s
$ LAB_TARGET=solution pytest -q
...............                                                          [100%]
15 passed in 9.61s
```

**Full teardown, confirmed empty:**

```
$ docker ps -a --format "{{.Names}}" | grep mlops-real-container
(empty)
$ docker images --format "{{.Repository}}" | grep mlops-real-container
(empty)
```

## Stretch goals

- Add a `check_resource_no_new_privileges` lint rule and a matching `--security-opt=no-new-privileges`
  requirement, then confirm it live with `docker inspect`.
- Make `train_model.py` accept a `RANDOM_STATE` build ARG and add a lint rule that the Dockerfile pins
  it, so the image is reproducible bit-for-bit across rebuilds.
- Add a multi-arch build check (`docker buildx build --platform linux/amd64,linux/arm64`) and a lint
  rule that the Dockerfile has no arch-specific hardcoded paths.
- Extend `scripts/kind_demo.sh` with a readiness-probe failure injection (temporarily rename
  `MODEL_PATH`) and watch Kubernetes take the pod out of the Service's endpoints.

## How this comes up in interviews

- "Why multi-stage builds?" (keep compilers/build tools and training data out of the image that
  actually runs in production - smaller attack surface, smaller image, faster pulls and cold starts.)
- "Why does the container need to run as non-root?" (a container breakout or a dependency RCE lands as
  root on the host's kernel namespace otherwise - non-root is a real, load-bearing blast-radius limit,
  not a checkbox.)
- "What's the difference between a Docker `HEALTHCHECK` and a Kubernetes readiness/liveness probe?"
  (`HEALTHCHECK` only affects `docker ps`'s reported status and is invisible to a scheduler that isn't
  Docker Swarm; Kubernetes has its own, separate probes that actually gate traffic and restarts, which
  is why `k8s/deployment.yaml` defines both explicitly rather than relying on the image's HEALTHCHECK.)
- "Walk me through a rolling update and how you'd roll it back." (`maxSurge`/`maxUnavailable` bound how
  much capacity changes during the rollout; `kubectl rollout status` waits for the new ReplicaSet to
  become ready before the old one scales down; `kubectl rollout undo` reverts to the previous
  ReplicaSet's pod template - exactly what `scripts/kind_demo.sh` does against a real cluster.)
- "Why copy `requirements.txt` before the rest of the source?" (Docker layer caching is content-hash
  based per instruction; if source is copied first, any code change invalidates every layer after it,
  including the expensive `pip install`, on every single build.)

## What this lab does not cover

- Image scanning (Trivy/Grype), SBOM generation, or signing (cosign) - real supply-chain hardening
  beyond "no secrets in the Dockerfile."
- A container registry (push/pull, auth, retention policies) - `kind load docker-image` sidesteps this
  entirely for the local demo, which a real cluster cannot do.
- Kubernetes Secrets/ConfigMaps, NetworkPolicies, or an Ingress/TLS layer in front of the Service.
- Horizontal Pod Autoscaling, PodDisruptionBudgets, or multi-node/multi-zone scheduling constraints.
- Real load testing of the rolling update (the `kind_demo.sh` rollout is verified via `rollout
  status`/`history`, not via concurrent traffic asserting zero dropped requests).
