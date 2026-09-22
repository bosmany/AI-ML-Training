# Lab: Real monitoring stack (FastAPI + Prometheus + Grafana)

Instrument a real FastAPI model-serving app with `prometheus_client`, then bring up a **real**
`docker-compose` stack - the actual `prom/prometheus` and `grafana/grafana` images, not a mock or an
in-process fake - that scrapes the app's `/metrics` endpoint, evaluates a real Prometheus alerting
rule, and shows the numbers on a pre-provisioned Grafana dashboard. The automated tests bring the
real stack up, hit the real app to generate real load, query Prometheus's real HTTP API to assert
real numbers, force a real alert to fire, and tear the whole stack down (`docker compose down -v`).

This lab stands on its own: it ships a small model-serving app (predict-from-mean-of-features) so it
does not depend on any other lab being present.

## Why it matters in a real job

"We have Grafana" means nothing if nobody wired the app to expose metrics, nobody wrote an alert
rule with a sane threshold and `for:` duration, and nobody has ever watched it actually fire. This lab
makes you do all three, against real containers, and prove it with real API responses instead of a
screenshot.

## Prerequisites (course chapters)

- [MLOps practice 4: monitoring and drift](../../mlops-practice/mp04-monitoring-and-drift.html)
- [MLOps ch. 32: MLOps fundamentals capstone](../../mlops/ch32-mlops-fundamentals-capstone.html)
- [FastAPI ch. 36: fundamentals](../../fastapi/ch36-fastapi-fundamentals.html)
- [Systems 4: Linux, Docker, Kubernetes](../../systems/sf04-linux-docker-kubernetes.html)

## What's graded automatically vs. what needs Docker on your machine

**Everything in this lab is graded automatically, for real - there is no offline/hermetic half.**
Unlike the 3 "needs your own external account" labs in this batch, this one needs nothing but a local
Docker daemon (no API key, no cloud account). `pytest` itself starts the real stack, drives it, and
tears it down; you do not need Prometheus or Grafana installed on your host, only Docker.

```bash
cd labs/mlops-real-monitoring-stack
pip install -r requirements.txt          # fastapi, uvicorn, prometheus-client, requests, pytest
pytest -q                                # starter: 4 tests error/fail - app returns 500 until implemented
LAB_TARGET=solution pytest -q            # maintainers / CI: reference solution passes, real Docker required
```

Each run takes 45-90s of wall time: it really builds a Docker image, really starts 3 containers,
really waits for Prometheus to scrape, really sends HTTP load, and really tears everything down. It
needs Docker (no sudo required) and network access to pull `python:3.11-slim`, `prom/prometheus:v2.55.1`
and `grafana/grafana:11.3.0` the first time (cached after that).

Edit only `starter/lab/{app,metrics}.py`. `starter/Dockerfile`, `docker-compose.yml`, the Prometheus
config and the Grafana provisioning are already complete and identical between starter and solution -
only the *app code* is a stub in starter.

## The stack

```
docker-compose.yml            # app (built from starter/ or solution/ Dockerfile via $LAB_TARGET) + prometheus + grafana
docker/prometheus/prometheus.yml     # 2s scrape/eval interval, scrapes app:8000/metrics
docker/prometheus/alert.rules.yml    # HighPredictRequestLatency, HighPredictionDrift
docker/grafana/provisioning/...      # datasource (Prometheus, pre-wired) + dashboard provider
docker/grafana/dashboards/app_dashboard.json   # request rate, p95 latency, drift score, total requests
starter/lab/app.py, metrics.py       # implement the TODOs
solution/lab/app.py, metrics.py      # reference implementation
tests/conftest.py                    # session fixture: docker compose up --build, wait healthy, ..., down -v
tests/test_monitoring_stack.py       # real assertions against the real running stack
scripts/manual_verify.sh             # the same real steps, runnable by hand outside pytest
```

### The app (`lab/app.py`)

| Endpoint | Behaviour |
| --- | --- |
| `GET /health` | `{"status": "ok"}` |
| `POST /predict` `{"features": [floats], "simulate_latency_seconds": 0.0}` | trivial "model" (`mean(features) * 2`), publishes the drift gauge, optionally sleeps for `simulate_latency_seconds` (this is how the test induces a **real** wall-clock latency spike instead of hand-waving one) |
| `GET /metrics` | real `prometheus_client` exposition text |

### The metrics (`lab/metrics.py`)

| Metric | Type | Labels |
| --- | --- | --- |
| `http_requests_total` | Counter | `method`, `endpoint`, `status_code` |
| `http_request_duration_seconds` | Histogram | `endpoint` |
| `prediction_drift_score` | Gauge | none - most recent `\|mean(features) - reference_mean\|` |

### The alert rules (`docker/prometheus/alert.rules.yml`)

```yaml
- alert: HighPredictRequestLatency
  expr: histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{endpoint="/predict"}[15s])) by (le)) > 1
  for: 6s
- alert: HighPredictionDrift
  expr: prediction_drift_score > 5
  for: 6s
```

## Tasks

1. **`metrics.py`** - declare the Counter/Histogram/Gauge with the exact names/labels above, implement
   `record_request`, `update_drift`, `render_latest`.
2. **`app.py`** - the ASGI middleware that times every request and calls `metrics.record_request`
   (including on exceptions, with status 500, then re-raise), and the `/predict` handler that sleeps
   when asked, computes the trivial prediction, and calls `metrics.update_drift`.

## Hints

<details><summary>Why does the histogram need buckets up to 5s?</summary>

The test induces a real ~1.2s sleep to trigger the latency alert. `histogram_quantile` interpolates
inside whichever bucket the value falls into - if your largest bucket boundary were, say, 0.5s, every
slow request would be lumped into the `+Inf` bucket and the p95 estimate would be unreliable. Buckets
here go up to 5s specifically so a ~1.2s real spike lands in a normal, informative bucket.
</details>

<details><summary>Why is the Gauge not per-request-reset?</summary>

A Gauge holds its last `.set()` value until the next one - it does not decay on its own. That is
exactly what lets a single "far from reference" request keep `prediction_drift_score` above threshold
long enough for `for: 6s` to be satisfied over several Prometheus evaluation cycles, without you having
to keep sending requests.
</details>

<details><summary>Counter/Histogram label cardinality</summary>

Both metrics are labelled by `endpoint`, which here is a small, fixed set of literal paths
(`/health`, `/predict`, `/metrics`) - never label Prometheus metrics with unbounded values like a user
ID or a full URL with a query string; that is what causes real Prometheus cardinality explosions in
production.
</details>

## Real output captured from an actual run (2026-09-22)

Everything below is pasted from an actual `docker compose up` / `curl` / `pytest` session against this
lab's `solution/` code - nothing here was typed by hand without running it first.

**Bringing the real stack up:**

```
$ LAB_TARGET=solution docker compose -f docker-compose.yml up -d --build
 Image mlops-real-monitoring-stack-app:solution Built
 Network mlops-real-monitoring-stack_default Created
 Container mlops-real-monitoring-stack-app-1 Started
 Container mlops-real-monitoring-stack-prometheus-1 Started
 Container mlops-real-monitoring-stack-grafana-1 Started

$ docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
NAMES                                      STATUS                    PORTS
mlops-real-monitoring-stack-grafana-1      Up 10 seconds             0.0.0.0:13000->3000/tcp
mlops-real-monitoring-stack-prometheus-1   Up 10 seconds             0.0.0.0:19090->9090/tcp
mlops-real-monitoring-stack-app-1          Up 10 seconds (healthy)   0.0.0.0:18000->8000/tcp

$ curl -s http://127.0.0.1:18000/health
{"status":"ok"}
$ curl -s http://127.0.0.1:19090/-/ready
Prometheus Server is Ready.
```

**Real scrape target, confirmed via Prometheus's own API:**

```
$ curl -s http://127.0.0.1:19090/api/v1/targets | ... 
"job": "fastapi-app"   "scrapeUrl": "http://app:8000/metrics"   "lastError": ""   "health": "up"
```

**Real load, real counter/histogram growth (25 real `/predict` requests):**

```
$ for i in $(seq 1 25); do curl -s -X POST http://127.0.0.1:18000/predict \
    -H 'Content-Type: application/json' -d '{"features": [0.1, -0.05, 0.02]}' >/dev/null; done
$ sleep 6
$ curl -s -G http://127.0.0.1:19090/api/v1/query \
    --data-urlencode 'query=http_requests_total{endpoint="/predict"}'
{"status":"success","data":{"resultType":"vector","result":[{"metric":{...,"status_code":"200"},"value":[1790047966.730,"25"]}]}}
$ curl -s -G http://127.0.0.1:19090/api/v1/query \
    --data-urlencode 'query=http_request_duration_seconds_count{endpoint="/predict"}'
{"status":"success","data":{"resultType":"vector","result":[{"metric":{...},"value":[1790047966.736,"25"]}]}}
```

25 requests sent -> `http_requests_total{endpoint="/predict"}` == 25, `..._count{endpoint="/predict"}` == 25.

**Real induced latency spike, real alert transition `none -> pending -> firing`:**

```
$ for i in $(seq 1 25); do
    curl -s -X POST http://127.0.0.1:18000/predict -d '{"features":[0.0],"simulate_latency_seconds":1.2}' >/dev/null
    # poll /api/v1/alerts for HighPredictRequestLatency's state
  done
iter=1 state=none    elapsed=1s
iter=2 state=none    elapsed=2s
iter=3 state=pending elapsed=4s
iter=7 state=pending elapsed=9s
iter=8 state=firing  elapsed=10s

$ curl -s http://127.0.0.1:19090/api/v1/alerts
{
  "data": {"alerts": [{
    "labels": {"alertname": "HighPredictRequestLatency", "severity": "critical"},
    "state": "firing",
    "activeAt": "2026-09-22T03:32:54.678236949Z",
    "value": "1.475e+00"
  }]}
}
```

Real p95 latency observed by Prometheus: **1.475s** (threshold was 1s) - the alert really fired 10s
after the real slow requests started, matching the rule's `for: 6s` plus scrape/eval delay.

**Real drift spike, real alert firing:**

```
$ curl -s -X POST http://127.0.0.1:18000/predict -d '{"features":[100.0,100.0,100.0]}'
{"prediction":200.0,"drift_score":100.0,"model_version":"v1"}
# polling /api/v1/alerts for HighPredictionDrift:
iter=1 state=none    elapsed=0s
iter=2 state=pending elapsed=2s
iter=5 state=firing  elapsed=8s

$ curl -s http://127.0.0.1:19090/api/v1/alerts | ... HighPredictionDrift firing 1e+02
```

Real drift score **100.0** (threshold was 5) fired the alert in 8s.

**Grafana really provisioned, both the datasource and the dashboard, with no manual clicking:**

```
$ curl -s -u admin:admin http://127.0.0.1:13000/api/health
{"database": "ok", "version": "11.3.0", ...}
$ curl -s -u admin:admin http://127.0.0.1:13000/api/datasources
[{"name": "Prometheus", "type": "prometheus", "url": "http://prometheus:9090", "isDefault": true, ...}]
$ curl -s -u admin:admin "http://127.0.0.1:13000/api/search?type=dash-db"
[{"uid": "fastapi-app-real-monitoring", "title": "FastAPI model-serving app", ...}]
```

**Full automated pytest run against `solution/` (real Docker, real stack, real teardown):**

```
$ LAB_TARGET=solution pytest -q
....                                                                     [100%]
4 passed in 47.85s
```

**Full teardown, confirmed empty:**

```
$ docker compose -f docker-compose.yml down -v
 Container mlops-real-monitoring-stack-grafana-1 Removed
 Container mlops-real-monitoring-stack-prometheus-1 Removed
 Container mlops-real-monitoring-stack-app-1 Removed
 Network mlops-real-monitoring-stack_default Removed
$ docker ps -a --format "{{.Names}}"
(empty)
$ docker network ls --format "{{.Name}}" | grep mlops
(empty)
```

## Optional: watch it in Grafana yourself

```bash
cd labs/mlops-real-monitoring-stack
LAB_TARGET=solution docker compose up -d --build
# open http://localhost:13000 (admin/admin, or anonymous viewer access is enabled)
# the "FastAPI model-serving app" dashboard is already there - generate load with:
for i in $(seq 1 50); do curl -s -X POST localhost:18000/predict -d '{"features":[0.1]}' >/dev/null; done
# when done:
docker compose down -v
```

## Stretch goals

- Add a `HighErrorRate` alert on `rate(http_requests_total{status_code=~"5.."}[30s])` and trigger it by
  sending malformed JSON.
- Add an Alertmanager service to the compose stack and assert a real webhook receiver got a POST.
- Replace the trivial mean-based "model" with the sklearn model style from the experiment-tracking
  lab and compute drift with PSI instead of a raw mean distance.
- Add a `docker-compose.override.yml` that mounts the dashboard read-write for live editing in Grafana.

## How this comes up in interviews

- "Walk me through what happens from a slow request to a page." (histogram bucket -> `rate()` ->
  `histogram_quantile()` -> `for:` duration -> Alertmanager/notification channel.)
- "Why use a Histogram instead of computing p95 in application code?" (Prometheus aggregates across
  instances/replicas from the raw buckets; an app-computed p95 cannot be re-aggregated correctly.)
- "What's the difference between `pending` and `firing`?" (the rule condition became true at `pending`;
  it must stay true for the whole `for:` duration before Alertmanager is notified - this is what stops
  a single noisy scrape from paging someone.)
- "How would you test alerting logic without waiting minutes for a real page?" (short `scrape_interval`/
  `evaluation_interval`/`for:` in a lower environment, exactly as this lab does, or `promtool test rules`
  for pure unit tests of the rule expressions.)

## What this lab does not cover

- Alertmanager, notification channels (Slack/PagerDuty/email) and alert routing/silencing.
- Multi-instance scraping, service discovery, or long-term metrics storage (Thanos/Cortex/Mimir).
- Authentication/TLS on Prometheus or Grafana (both run wide open here - fine for a local lab, not for
  production).
- Real model drift detection (PSI/KS/chi-square, as in `mlops-drift-monitor`) - the "drift" here is a
  deliberately simple stand-in so the alerting mechanics stay the focus.
