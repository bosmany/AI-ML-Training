# Lab: Experiment tracker and model registry (SQLite)

Build a small MLflow-like system from scratch: a **tracker** (runs, immutable params, stepped metrics,
artifact hashes, run comparison, best-run selection) and a **registry** (model versions, stages, promotion
gates, rollback, lineage) on real SQLite, plus a CLI. The tests read and write real database files.

## Why it matters in a real job

"How do you know which model is in production, what data and code produced it, and how do you roll it back?"
is the core MLOps interview question. Teams that cannot answer it lose days debugging regressions. Building
the mechanism yourself shows what MLflow / SageMaker Model Registry / Vertex do for you, and pins the subtle
parts: immutability, deterministic "best run", atomic promotion, and float-safe gates.

## Prerequisites (course chapters)

- [Reproducibility and data validation](../../mlops-practice/mp01-reproducibility-data-validation.html)
- [Experiment tracking and model registry](../../mlops-practice/mp02-experiment-tracking-model-registry.html)
- [Model deployment](../../mlops/ch31-model-deployment.html)
- [Monitoring and drift](../../mlops-practice/mp04-monitoring-and-drift.html) (for the rollback story)

## Run it

```bash
cd labs/mlops-experiment-tracker
pip install -r requirements.txt          # only pytest: the lab uses the standard library (sqlite3)
pytest -q                                # starter: fails until you implement it
LAB_TARGET=solution pytest -q            # maintainers / CI: reference solution passes
```

Edit only `starter/lab/tracker.py`, `starter/lab/registry.py` and `starter/lab/cli.py`. `errors.py`,
`models.py` and `db.py` (schema + connection helper) are provided - read them first. Tests import
`from lab import ...` and pick `starter/` or `solution/` via `LAB_TARGET`.

Try your CLI by hand once the tests pass:

```bash
cd starter
RUN=$(python -m lab --db /tmp/demo.db start --experiment churn --dataset-hash sha256:abc --code-version git:123)
python -m lab --db /tmp/demo.db log-metric $RUN acc 0.93 && python -m lab --db /tmp/demo.db end $RUN
python -m lab --db /tmp/demo.db register --model churn --run $RUN
```

## Tasks

1. **Tracker basics** - `start_run`, `end_run`, `log_param`, `log_metric`, `set_tag`, `get_run`. Params are
   stored as strings and are immutable (re-logging the same value is fine); finished runs are frozen.
2. **Metric semantics** - one row per `(key, step)` (re-logging a step replaces it); a run's *final* metric is the
   value at the highest step; NaN/inf are rejected.
3. **Artifacts** - `log_artifact` streams a file in chunks and stores its SHA-256.
4. **Comparison** - `compare_runs` (metric table + only the params that differ) and `best_run` (max/min, only
   FINISHED runs, deterministic tie-break: earliest start, then lowest run id).
5. **Registry** - `register_version` (needs a FINISHED run with dataset hash and code version), stage machine
   `None -> Staging -> Production -> Archived`, `lineage`, `history`.
6. **Promotion gates** - metric threshold; must beat current production by a margin (**float-safe**:
   `0.938 - 0.933 == 0.004999999999999893`, so a naive `>= 0.005` rejects a valid model); validated flag; no open
   data-quality flags. Report *all* failures at once. Promotion archives the old production version atomically.
7. **Rollback** - restore the version that production superseded, without re-running the gates.
8. **CLI** - `main(argv) -> int` with exit codes 0 / 1 (domain error) / 2 (usage).

## Hints

<details><summary>How do I get the final metric per key in one SQL query?</summary>

Correlated subquery: `SELECT m.key, m.value FROM metrics m WHERE m.run_id = ? AND m.step =
(SELECT MAX(step) FROM metrics WHERE run_id = m.run_id AND key = m.key)`.
</details>

<details><summary>Upsert in SQLite</summary>

`INSERT INTO metrics (...) VALUES (?, ?, ?, ?) ON CONFLICT(run_id, key, step) DO UPDATE SET value = excluded.value`
(SQLite 3.24+, which Python ships with).
</details>

<details><summary>Why compare rounded values in best_run?</summary>

`0.5` and `0.5 + 1e-15` are the "same" result to a human but not to `==`. Rounding to 12 decimals makes the tie
rule (start time, then run id) apply, so the answer does not depend on floating-point noise or insert order.
</details>

<details><summary>A transaction for promotion</summary>

`with self._conn:` commits on success and rolls back on an exception, so "archive the old production version and
promote the new one" can never half-happen.
</details>

<details><summary>sqlite3.OperationalError: database is locked</summary>

Two connections to one file are fine as long as each write is committed (`with self._conn:`). Never leave a
transaction open between method calls.
</details>

## Optional: the same thing in real MLflow (reference only - mlflow is NOT required)

If you later install MLflow (`pip install mlflow`), the concepts map like this:

| This lab | MLflow |
| --- | --- |
| `Tracker.start_run` / `end_run` | `mlflow.start_run()` (context manager) / `mlflow.end_run()` |
| `log_param` (immutable) | `mlflow.log_param("lr", 0.01)` - MLflow also refuses to change a param's value |
| `log_metric(key, value, step)` | `mlflow.log_metric("acc", 0.93, step=3)` |
| `set_tag` | `mlflow.set_tag("owner", "ana")` |
| `log_artifact(path)` (SHA-256) | `mlflow.log_artifact(path)` (copies the file; you would add a hash yourself) |
| `best_run` | `mlflow.search_runs(order_by=["metrics.acc DESC"], max_results=1)` |
| `Registry.register_version` | `mlflow.register_model("runs:/<run_id>/model", "churn")` |
| stages + `transition` | `MlflowClient().transition_model_version_stage(...)` (stages are deprecated in MLflow 2.9+ in favour of *aliases*: `set_registered_model_alias(name, "champion", version)`) |
| rollback | re-point the alias/stage to the previous version |
| lineage (dataset hash, code version) | run tags such as `mlflow.source.git.commit` and `mlflow.log_input(dataset)` |

What MLflow does **not** give you out of the box is the policy layer (promotion gates, float-safe margins,
open-quality-flag blocking) - teams write exactly the kind of code you wrote here around it.

## Stretch goals

- Add `search_runs(experiment, filter)` supporting `metrics.acc > 0.9 and params.model = "xgb"`.
- Add nested runs (parent/child) for hyperparameter sweeps.
- Store artifacts content-addressed on disk (`artifacts/<sha256[:2]>/<sha256>`) and verify the hash on load.
- Add optimistic concurrency: two people promoting at once must not both win.

## How this comes up in interviews

- "Which model is in production, and what data + code produced it?" (lineage.)
- "A new model has 0.938 vs production 0.933 and our margin is 0.005 - why did CI reject it?" (float error.)
- "How do you make 'best run' reproducible?" (ties, final vs best step, only finished runs.)
- "Design a promotion policy." (thresholds, margins, validation, data-quality holds, audit history, rollback.)
- "Why are params immutable but tags mutable?"
