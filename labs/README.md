# Hands-on labs

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/bosmany/ai-ml-zero-to-hero)

One-command setup anywhere: `make bootstrap && make doctor && make labs` (Codespaces/devcontainer does this for you). Run a lab: `make grade LAB=<folder>`; check the reference: `make grade LAB=<folder> TARGET=solution`; local Kubernetes for k8s labs: `make kind`.


The chapters in this course run in the browser, which cannot start a real server, talk to AWS, drive Kubernetes
or run Docker. These labs fill that gap: each one is a small **real Python project** that you run on your own
machine, graded by `pytest`, using the same libraries you would use at work (FastAPI, SQLAlchemy, boto3, subprocess,
prometheus_client, scipy...).

Most labs are fully hermetic (no network, no real cloud account, no real cluster). The `-real-*` labs are
different on purpose: they spin up real local infrastructure you already have (Docker, a real MLflow server, a
real Prometheus/Grafana stack, a real LocalStack container) so the graded tests exercise the real thing, not a
mock. Three labs (`agentic-ai-real-llm-tool-calling`, `rag-real-vector-db-deploy`, `fastapi-real-deploy-cicd-live`)
go one step further: everything graded by `pytest` still runs offline with zero account needed, but each has a
clearly separate "go live" path that only works once *you* add your own free API key or account (a Groq key, a
Hugging Face account, a Fly.io account+token) — each lab's README says exactly which env var/secret to set and
where to get it, and no output is ever shown as real unless it was actually captured from a real run.

## The labs

| Lab | Difficulty | Time | Skills | Read first |
| --- | --- | --- | --- | --- |
| [`devops-log-analyzer`](devops-log-analyzer/README.md) | Easy-Medium | 2-3 h | generators / streaming, regex, argparse, percentiles, sliding windows, exit codes for CI | [DevOps 1: log parsing](../devops/do01-log-parsing-text-processing.html), [DevOps 3: resilience](../devops/do03-automation-scripts-resilience.html), [Python ch. 7](../python/ch07-python-devops-apis.html) |
| [`devops-aws-audit-moto`](devops-aws-audit-moto/README.md) | Medium | 3-4 h | real boto3 vs moto, pagination, `ClientError` + backoff, injected clock, JSON/Markdown reports | [DevOps 4: cloud ops](../devops/do04-cloud-and-container-ops.html), [DevOps 3](../devops/do03-automation-scripts-resilience.html), [Python ch. 7](../python/ch07-python-devops-apis.html) |
| [`devops-k8s-triage`](devops-k8s-triage/README.md) | Medium | 3-4 h | kubectl JSON, quantity parsing, QoS, pod/node diagnosis, safe `subprocess` with an injectable runner | [Systems 4: Linux, Docker, Kubernetes](../systems/sf04-linux-docker-kubernetes.html), [DevOps 4](../devops/do04-cloud-and-container-ops.html) |
| [`devops-backup-janitor`](devops-backup-janitor/README.md) | Medium-Hard | 3-5 h | retention policies, dry-run, atomic writes, lock files, path-traversal safety, retry with jitter | [DevOps 3: resilience](../devops/do03-automation-scripts-resilience.html), [Python ch. 5](../python/ch05-oop-files-errors.html) |
| [`fastapi-candidate-api`](fastapi-candidate-api/README.md) | Medium-Hard | 4-6 h | FastAPI, async SQLAlchemy 2, Pydantic v2, JWT auth and roles, pagination, error format, middleware | [FastAPI ch. 36-40](../fastapi/ch36-fastapi-fundamentals.html) |
| [`fastapi-deploy-cicd`](fastapi-deploy-cicd/README.md) | Easy-Medium | 2-3 h | hardened Dockerfile, Compose, GitHub Actions, static policy tests | [FastAPI ch. 41: capstone and deployment](../fastapi/ch41-fastapi-capstone-deployment.html), [Systems 4](../systems/sf04-linux-docker-kubernetes.html) |
| [`mlops-experiment-tracker`](mlops-experiment-tracker/README.md) | Medium | 3-4 h | experiment tracking, model registry, reproducibility | [MLOps practice 2: experiment tracking](../mlops-practice/mp02-experiment-tracking-model-registry.html), [MLOps practice 1](../mlops-practice/mp01-reproducibility-data-validation.html) |
| [`mlops-drift-monitor`](mlops-drift-monitor/README.md) | Medium-Hard | 3-5 h | drift statistics with scipy, metrics with prometheus_client, monitoring | [MLOps practice 4: monitoring and drift](../mlops-practice/mp04-monitoring-and-drift.html), [MLOps ch. 32](../mlops/ch32-mlops-fundamentals-capstone.html) |
| [`fastapi-url-shortener`](fastapi-url-shortener/README.md) | Medium | 4-6 h | FastAPI, SQLAlchemy 2, unique-index collision retry, URL validation, 301/302/404/410, expiry with a fake clock, click counting, pagination | [FastAPI ch. 36-38](../fastapi/ch36-fastapi-fundamentals.html), [Systems 1: APIs and HTTP](../systems/sf01-apis-http-fundamentals.html) |
| [`devops-config-auditor`](devops-config-auditor/README.md) | Medium | 5-7 h | PyYAML `safe_load`, JSON pointers and line numbers, rule engine, docker-compose and Kubernetes policies, JSON/text reports, CI exit codes | [DevOps 2: config formats](../devops/do02-config-yaml-json-toml.html), [DevOps 4](../devops/do04-cloud-and-container-ops.html), [Python ch. 6](../python/ch06-professional-python.html) |
| [`python-expense-tracker`](python-expense-tracker/README.md) | Easy-Medium | 4-6 h | argparse subcommands, money as integer cents, atomic JSON writes, corrupt-file handling, exit codes, monthly budgets | [Python ch. 3](../python/ch03-functions-modules.html), [Python ch. 5](../python/ch05-oop-files-errors.html), [Python ch. 6](../python/ch06-professional-python.html), [OOP 4](../python/oop04-composition-dataclasses-design.html) |
| [`python-async-link-checker`](python-async-link-checker/README.md) | Hard | 6-8 h | asyncio, semaphore-bounded concurrency, httpx timeouts, HEAD/GET fallback, redirects, retries with backoff, cancellation, local fixture HTTP server | [Python ch. 6](../python/ch06-professional-python.html), [Python ch. 7](../python/ch07-python-devops-apis.html), [Systems 1: APIs and HTTP](../systems/sf01-apis-http-fundamentals.html), [Systems 2: networking](../systems/sf02-networking-microservices.html) |
| [`agentic-ai-real-llm-tool-calling`](agentic-ai-real-llm-tool-calling/README.md) | Medium-Hard | 4-6 h | real LLM tool calling (Groq/OpenAI SDK), ReAct loop, prompt-injection guardrail, trimmed conversation memory, token/cost tracking, streaming reassembly | [Projects ch. 34: Agentic AI system](../projects/ch34-agentic-ai-system.html), [Python ch. 6](../python/ch06-professional-python.html) |
| [`mlops-real-experiment-tracking`](mlops-real-experiment-tracking/README.md) | Medium | 4-6 h | a real local MLflow server, real sklearn training runs, real model registry promotion, querying the real REST API | [MLOps practice 2: experiment tracking](../mlops-practice/mp02-experiment-tracking-model-registry.html) |
| [`mlops-real-container-deploy`](mlops-real-container-deploy/README.md) | Medium-Hard | 4-6 h | a real FastAPI model server, a real multi-stage Dockerfile built and run with `docker build`/`docker run`, health checks, non-root; k8s manifests and rolling updates documented for `kind` | [MLOps ch. 31: model deployment](../mlops/ch31-model-deployment.html), [Systems 4](../systems/sf04-linux-docker-kubernetes.html) |
| [`mlops-real-monitoring-stack`](mlops-real-monitoring-stack/README.md) | Medium-Hard | 4-6 h | a real Prometheus + Grafana stack via docker-compose, a real `/metrics` endpoint, generating real load, a real alert rule that actually fires | [MLOps practice 4: monitoring and drift](../mlops-practice/mp04-monitoring-and-drift.html) |
| [`devops-real-terraform-localstack`](devops-real-terraform-localstack/README.md) | Medium-Hard | 4-6 h | real Terraform HCL (S3, IAM, Lambda) against a real local LocalStack container, boto3 verification, a real Lambda invoke | [DevOps 4: cloud ops](../devops/do04-cloud-and-container-ops.html) |
| [`rag-real-vector-db-deploy`](rag-real-vector-db-deploy/README.md) | Medium-Hard | 5-7 h | a real local vector DB (chromadb), real retrieval + grounding, a Hugging Face Spaces app (Gradio) you deploy yourself for a public URL | [Projects ch. 35: RAG chatbot, deployed](../projects/ch35-rag-chatbot-deployed.html) |
| [`fastapi-real-deploy-cicd-live`](fastapi-real-deploy-cicd-live/README.md) | Medium | 3-5 h | a real `fly.toml` + GitHub Actions workflow (tests gate the deploy, health check, rollback on failure) that goes live once you add your own Fly.io account and secret | [FastAPI ch. 41: capstone and deployment](../fastapi/ch41-fastapi-capstone-deployment.html) |

Times are for someone who has read the linked chapters. Each lab README has the goal, numbered tasks, collapsible
hints, stretch goals, how the topic comes up in interviews and an honest "what this lab does not cover" section.

One exception to "tests never touch the network": `agentic-ai-real-llm-tool-calling` has an opt-in `-m live` tier
(3 tests, real Groq API, free key) that is excluded by default and never runs as part of grading or `run_all.sh`.

## Setup

You need Python 3.11 or newer.

```bash
cd labs/<lab-name>
python -m venv .venv && source .venv/bin/activate   # one venv per lab keeps dependencies clean
pip install -r requirements.txt
pytest -q
```

Every lab has the same layout:

```
labs/<lab-name>/
  README.md          goal, tasks, hints, stretch goals
  requirements.txt   the libraries this lab needs
  starter/lab/       YOUR code: stubs with docstrings and TODOs (they raise NotImplementedError)
  solution/lab/      reference implementation - look only after you tried
  tests/             pytest tests; they do `from lab import ...`
```

### The `LAB_TARGET` convention

`tests/conftest.py` in each lab reads the environment variable `LAB_TARGET` (default `starter`) and puts
`labs/<lab>/<LAB_TARGET>/` first on `sys.path`, so `from lab import ...` loads your code or the reference code
without the tests knowing which.

```bash
pytest -q                        # runs against starter/  -> everything fails until you implement it
LAB_TARGET=solution pytest -q    # runs against solution/ -> everything passes (maintainers / CI)
```

## How to work

1. Read the lab README completely (goal, provided vs. what you write, tasks).
2. Run `pytest -q` and read the first failure: test names state the behaviour being pinned and the assertion
   messages explain what is wrong.
3. Implement `starter/lab/` one task at a time (`pytest -q -x` stops at the first failure; `pytest -k name` runs one test).
4. Only after a real attempt, open the hints, then compare with `solution/`. Reading a solution you have not tried to
   write teaches little; the hints are collapsed on purpose.
5. Try the stretch goals and rehearse the "how this comes up in interviews" section out loud.

Edit only `starter/`. Never edit `tests/` to make them pass.

## Checking every lab (maintainers / CI)

```bash
labs/run_all.sh                          # all labs, current python (must have every requirements.txt installed)
labs/run_all.sh devops-log-analyzer      # only some labs
VENV=/tmp/labs-venv labs/run_all.sh      # isolated venv, requirements installed per lab
```

For each lab it runs the solution tests (must all pass) and the starter tests (must **all** fail), prints a table and
exits non-zero on any violation. A starter that passes a test by accident would let a learner believe they had
finished something they had not started.

## What the labs do not cover

- They are **local simulations**: `moto` is not AWS, fixtures are not a live cluster, and nothing here runs Docker
  itself. Each lab README lists its specific gaps; real systems add rate limits, eventual consistency, permissions
  and scale that no unit test reproduces.
- The tests check behaviour, not code style or design taste; a passing solution can still be badly structured.
- No lab covers production deployment, secrets management, observability platforms or on-call practice end to end.
- Tests are deterministic and fast on purpose (injected clocks, fake runners, `tmp_path`): they teach you to build
  code that is testable, but they will not find timing or concurrency bugs that only appear under real load.
