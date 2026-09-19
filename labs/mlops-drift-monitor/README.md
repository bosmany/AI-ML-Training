# Lab: Drift monitor service (PSI, KS, chi-square, hysteresis, Prometheus)

Build the monitoring service every production model needs: it receives batches of prediction logs
(`POST /ingest`), compares the recent window with the training data using **PSI**, **KS** and **chi-square**,
raises alerts with **hysteresis** so they do not flap, exposes real **Prometheus** metrics on `/metrics`, and
tells you on `/status` whether to retrain. Tests drive the real FastAPI app with hand-built arrays (no randomness).

## Why it matters in a real job

Models rot silently: inputs shift, upstream pipelines change units, a new category appears. Teams that ship
models are asked "how would you know it is degrading?" The answer is exactly this service: statistics with sensible
binning and epsilons, alerting that does not page at 3 a.m. for noise, and metrics wired into Prometheus/Grafana.

## Prerequisites (course chapters)

- [Monitoring and drift](../../mlops-practice/mp04-monitoring-and-drift.html)
- [Model deployment](../../mlops/ch31-model-deployment.html)
- [FastAPI fundamentals](../../fastapi/ch36-fastapi-fundamentals.html)
- [Testing, middleware, background tasks](../../fastapi/ch40-testing-middleware-background-tasks.html)

## Run it

```bash
cd labs/mlops-drift-monitor
pip install -r requirements.txt
pytest -q                                # starter: everything fails until you implement it
LAB_TARGET=solution pytest -q            # maintainers / CI: reference solution passes
```

Edit only `starter/lab/{stats,windows,alerts,monitor,metrics,api}.py`. `config.py`, `schemas.py` and `app.py`
(the app factory) are provided - read them first. Tests import `from lab import ...` and choose `starter/` or
`solution/` from `LAB_TARGET`.

## The service

| Endpoint | Behaviour |
| --- | --- |
| `POST /ingest` `{"rows": [{...}, ...]}` | validates, adds to the rolling window, evaluates drift once the window has `min_window_rows`; `422` with row-level messages for bad batches (nothing partially ingested) |
| `GET /metrics` | Prometheus text: `drift_feature_psi{feature}` (gauge), `drift_feature_alert{feature}` (gauge), `drift_ingested_rows_total` (counter), `drift_ingest_latency_seconds` (histogram) |
| `GET /status` | window state, per-feature statistics, firing alerts, and a retrain recommendation |

Rules: a numeric feature is *breached* when `PSI >= psi_threshold`; a categorical feature when the chi-square
p-value `< chi2_alpha`. An alert **fires after `fire_after` consecutive breached evaluations** and **clears after
`clear_after` consecutive healthy ones**. Recommendation: `retrain` if two or more features are firing (or one
firing numeric feature has `PSI >= psi_critical`), `investigate` if exactly one is firing, otherwise `none`.

## Tasks

1. **`stats.psi` / `psi_edges`** - quantile bins from the *reference* (collapse duplicate edges), open-ended outer
   bins, epsilon floor for empty bins, NaN handling.
2. **`stats.ks_test`, `stats.chi_square_test`** - `scipy.stats.ks_2samp`; a 2 x k contingency table over the
   union of categories (unseen categories count as drift) with `chi2_contingency(correction=False)`.
3. **`alerts.HysteresisAlert`** and **`windows.RollingWindow`**.
4. **`monitor.DriftMonitor`** - validation (no partial ingestion), minimum window size, evaluation, alert updates,
   recommendation, status.
5. **`metrics.DriftMetrics`** - a *per-instance* `CollectorRegistry` (see the hint about "Duplicated timeseries").
6. **`api`** - the three endpoints; only accepted batches touch the metrics.

## Hints

<details><summary>PSI formula and the epsilon</summary>

`PSI = sum((a_i - e_i) * ln(a_i / e_i))` where `e_i` is the reference share of bin `i` and `a_i` the current share.
If a bin is empty, `ln(0)` is `-inf` and you divide by zero, so floor every share at a small epsilon (1e-4). Rules of
thumb: < 0.1 stable, 0.1-0.25 moderate shift, > 0.25 major shift.
</details>

<details><summary>Which bin does a value equal to an edge go to?</summary>

Bins are `(edge[i-1], edge[i]]`: `np.searchsorted(edges, x, side="left")`. Add `-inf`/`+inf` implicitly by using
`minlength=len(edges)+1` so values outside the reference range are still counted.
</details>

<details><summary>ValueError: Duplicated timeseries in CollectorRegistry</summary>

Metrics registered on the global default registry collide the second time you build an app in one process (every
test after the first). Create `CollectorRegistry()` per `DriftMetrics` and pass `registry=` to every metric.
</details>

<details><summary>Counter name and the _total suffix</summary>

`Counter("drift_ingested_rows", ...)` is exposed as `drift_ingested_rows_total`; prometheus_client adds the suffix.
</details>

<details><summary>Why hysteresis?</summary>

A PSI hovering at 0.19-0.21 crosses a 0.2 threshold every window. Requiring N consecutive breaches to fire and M
healthy ones to clear turns a flapping signal into a stable one.
</details>

## Optional: run it for real

```bash
pip install uvicorn
cd starter && python - <<'PY'
import uvicorn
from lab.app import create_app
from lab.config import FeatureSpec, MonitorConfig
config = MonitorConfig(reference={"age": list(range(20, 70)), "plan": ["free"]*30 + ["pro"]*20},
                       features=(FeatureSpec("age", "numeric"), FeatureSpec("plan", "categorical")))
uvicorn.run(create_app(config), port=8000)
PY
# then POST batches to http://127.0.0.1:8000/ingest and point Prometheus at /metrics
```

## Stretch goals

- Add a Jensen-Shannon distance and compare its sensitivity to PSI on a small window.
- Add per-feature configurable thresholds and a Slack-style webhook when an alert fires (inject the sender).
- Track *prediction* drift and, when labels arrive later, accuracy over time.
- Persist windows to disk so a restart does not blind the monitor.

## How this comes up in interviews

- "How do you detect data drift? Explain PSI, and what happens with an empty bin."
- "KS vs chi-square vs PSI - when do you use which?" (continuous vs categorical; significance vs effect size.)
- "Why did your alert page five times in an hour?" (no hysteresis / window too small.)
- "Which Prometheus metric types would you use for ingest volume, drift score and latency?"
- "How do you test code that emits Prometheus metrics?" (per-app registry, parse the exposition text.)
