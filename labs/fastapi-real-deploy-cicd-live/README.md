# Lab: Ship it for real - Fly.io continuous deployment for the FastAPI service

This lab **extends [`labs/fastapi-deploy-cicd`](../fastapi-deploy-cicd/README.md)** (read it first - same
service, same house style). That lab stopped at "CI builds and pushes an image." This one adds the last
mile: a `fly.toml` and a `.github/workflows/deploy.yml` that actually ship a push to `main` to a live,
public URL on [Fly.io](https://fly.io) - health-checked after every deploy, with an automatic rollback if
the new release comes up unhealthy. A set of **static policy tests** (PyYAML + `tomllib`, no network, no
Fly.io account) checks the files against the rules a platform team enforces before trusting a workflow with
real deploy credentials.

## Why it matters in a real job

"It builds in CI" and "it's live for users" are two different milestones, and the gap between them is where
production incidents live: a workflow that deploys before tests pass, a health check that is missing (or so
naive it passes the moment the container *starts*, not when it can actually serve traffic), no rollback path
so a bad release just sits there, or a deploy token pasted into the YAML instead of read from a secret. This
lab pins exactly those mistakes, using Fly.io because it has a genuinely free tier and a clean GitHub Actions
story, so what you build here is something you could point at a real account today.

## Important: what is graded offline vs. what needs your own account

- **Everything `pytest` grades is 100% static and offline.** The tests parse `fly.toml` (TOML) and
  `deploy.yml` (YAML) as text and assert properties of them - no `flyctl`, no Docker, no network call, no
  Fly.io account. This sandbox has **no Fly.io account and no `FLY_API_TOKEN`**, so a real deploy was never
  attempted here, by design (see the spec this lab was built from: `LAB_TARGET=solution pytest` must pass
  with zero cost and zero credentials).
- **Making the workflow actually deploy** needs your own free Fly.io account and a repo secret named
  `FLY_API_TOKEN` - see "Go live for real" below. Until you add that secret, the workflow in your fork will
  fail at the `flyctl deploy` step with an authentication error, which is the expected, safe failure mode.

## Prerequisites (course chapters)

- [`fastapi-deploy-cicd`](../fastapi-deploy-cicd/README.md) - read this lab's files and README first; this
  lab assumes the same `Dockerfile` / `app/` / `requirements*.txt` sit in the repo root next to `fly.toml`.
- [FastAPI capstone and deployment](../../fastapi/ch41-fastapi-capstone-deployment.html)
- [Cloud and container ops](../../devops/do04-cloud-and-container-ops.html)
- [Automation scripts and resilience](../../devops/do03-automation-scripts-resilience.html)

## Run it

```bash
cd labs/fastapi-real-deploy-cicd-live
pip install -r requirements.txt          # pyyaml + pytest only (fly.toml is parsed with stdlib tomllib)
pytest -q                                # starter: everything fails until you write the files
LAB_TARGET=solution pytest -q            # maintainers / CI: the reference passes
(cd starter && python -m lab)            # friendlier report of every rule, with the reason
```

You edit **the files under `starter/assets/`**, not the Python package. `starter/lab/` contains the loaders
and linter the tests use (read `lab/lint.py` to see exactly what each rule checks). The tests import
`from lab import ...` and choose `starter/` or `solution/` from `LAB_TARGET`, exactly like `fastapi-deploy-cicd`.

## Files

```
starter/assets/
  fly.toml                          YOU WRITE (task 1)
  .github/workflows/deploy.yml      YOU WRITE (task 2)
```

`starter/assets/` is, conceptually, the root of your repository - the same root that already holds the
`Dockerfile`, `app/`, `requirements.txt` and `.github/workflows/ci.yml` from `fastapi-deploy-cicd`. In a real
repo these two files live next to those, not in a separate folder; they are split out here only so this
lab's tests can grade them in isolation.

## Tasks

1. **`fly.toml`** - `app = "<unique-name>"` (lowercase/digits/hyphens - it becomes `<name>.fly.dev`) and
   `primary_region`; an `[http_service]` with `internal_port` matching the port the app listens on (`8000`,
   same as the Dockerfile's `EXPOSE`/`CMD`) and `force_https = true`; at least one `[[http_service.checks]]`
   block with `method = "GET"`, `path = "/health"`, and `grace_period`/`interval`/`timeout` all set; a
   `[[vm]]` with an explicit `size`. Never put a secret in `[env]` - runtime secrets belong in
   `flyctl secrets set`, deploy credentials belong in the GitHub Actions secret store.
2. **`.github/workflows/deploy.yml`** - trigger only on `push` to `branches: [main]` (never `pull_request` /
   `pull_request_target` - a fork's PR must never run with access to `FLY_API_TOKEN`); top-level
   `permissions: contents: read`; a `test` job (checkout, `actions/setup-python` with `cache: pip`, install,
   `pytest tests/health_check.py`); a `deploy` job with `needs: test` that installs `flyctl`
   (`superfly/flyctl-actions/setup-flyctl`) and runs `flyctl deploy --remote-only` with `FLY_API_TOKEN` read
   from `${{ secrets.FLY_API_TOKEN }}`; a **health-check step that runs after the deploy step** and hits the
   deployed app's `/health` over HTTPS with retries (a machine that is still booting is not the same as a
   failed deploy); a **rollback step gated on `if: failure()`** that runs `flyctl releases rollback --yes` so
   a release that fails its health check does not stay live. Pin every action to a version tag or commit SHA;
   `timeout-minutes` on every job; credentials only via `${{ secrets.* }}`.

## Hints

<details><summary>Why forbid `pull_request` as a trigger here?</summary>

`fastapi-deploy-cicd`'s CI workflow *should* run on `pull_request` (you want tests on every PR). This
workflow is different: it holds `FLY_API_TOKEN`, a real deploy credential. If it ran on `pull_request`, a
malicious fork could open a PR that edits the workflow to exfiltrate the secret, or simply deploys its own
code to your app. Deploy workflows trigger on `push` to a protected branch only.
</details>

<details><summary>My health check "passes" the instant the container starts - is that enough?</summary>

No. `internal_port` being reachable just means the process is listening; it says nothing about whether the
app can actually serve a request (imagine a container that starts, then crash-loops on the first request
because a dependency is missing). That is exactly why the workflow has its *own* health-check step that
curls the public `/health` URL after `flyctl deploy` returns, with retries - Fly's internal check and your
CI's external check are two different layers, and this lab grades the CI one.
</details>

<details><summary>Why gate rollback on `if: failure()` instead of `if: always()`?</summary>

`always()` would roll back a perfectly good release too, every single time - self-defeating. `failure()`
runs the step only when an earlier step in the same job (the deploy or the health-check) actually failed,
which is the one case where rolling back is the right call.
</details>

<details><summary>Why is `on:` a boolean in my parsed workflow?</summary>

YAML 1.1 (PyYAML) turns the bare key `on` into `True`. `lab/workflow.py` converts it back; remember this
whenever you parse Actions files in Python.
</details>

<details><summary>What is `[[http_service.checks]]` vs `[http_service.checks]`?</summary>

Fly.io's current `fly.toml` format takes an *array* of check tables (so you can define more than one), which
in TOML is written `[[http_service.checks]]` (double brackets). `lab/flytoml.py`'s `http_service_checks()`
helper normalises either shape into a list for you.
</details>

## Go live for real

This cannot be exercised inside this sandbox (no Fly.io account exists here), but once you have your own
account it takes about five minutes:

1. Sign up at <https://fly.io> (no credit card needed for the free/hobby allowance) and install `flyctl`:
   `curl -L https://fly.io/install.sh | sh`, then `flyctl auth login`.
2. From the repo root (the one holding the `Dockerfile` from `fastapi-deploy-cicd` and your new `fly.toml`),
   create the app once: `flyctl apps create <the app name you put in fly.toml>` (or run `flyctl launch
   --no-deploy` and let it generate a `fly.toml`, then reconcile it with the one from this lab).
3. Mint a deploy token scoped to that app: `flyctl tokens create deploy -a <app-name>` (or
   `flyctl auth token` for a full-account token while you're experimenting).
4. In your GitHub repo: **Settings -> Secrets and variables -> Actions -> New repository secret**, name it
   `FLY_API_TOKEN`, and paste the token from step 3.
5. Push to `main`. `test` runs first; if it passes, `deploy` installs `flyctl`, runs `flyctl deploy
   --remote-only`, curls `https://<app-name>.fly.dev/health` with retries, and rolls the release back
   automatically if that health check (or the deploy itself) fails.

Example output blocks below are **illustrative - this is what a successful run looks like once you add your
key**, not captured output from this sandbox:

```
$ flyctl deploy --remote-only
==> Verifying app config
Validating /home/you/repo/fly.toml
✓ Configuration is valid
==> Building image
...
✓ Machine e784...  update succeeded
$ curl --fail --retry 10 --retry-delay 5 --retry-all-errors https://candidate-api.fly.dev/health
{"status":"ok"}
```

## Stretch goals

- Add a `staging` app and environment that deploys on every push to a `develop` branch, promoted to
  production only via a manual `workflow_dispatch` approval.
- Use `flyctl deploy --strategy bluegreen` and only cut traffic over after the health check passes.
- Add a Slack/Discord notification step on rollback so a failed deploy pages someone.
- Pin the `flyctl` version explicitly (`superfly/flyctl-actions/setup-flyctl@1.5` with `version:` pinned too)
  and add Dependabot for the `github-actions` ecosystem.
- Extend the cross-file check to also compare `fly.toml`'s `internal_port` against the Dockerfile's `EXPOSE`
  from `fastapi-deploy-cicd`.

## How this comes up in interviews

- "Walk me through what happens between `git push` and your users seeing the change." (test gate, build,
  deploy, health check, rollback - and why each step exists.)
- "Why should a deploy workflow never trigger on `pull_request`?" (secrets reaching untrusted fork code.)
- "What's the difference between a container's own health check and a post-deploy health check in CI?"
  (readiness to accept traffic from *inside* the platform vs. an end-to-end check from *outside* it.)
- "Your deploy just went out and users are getting 500s - what does your pipeline do automatically?"
  (health-check failure -> `if: failure()` rollback step -> previous release restored without a human paged
  at 3am.)
- "Why read the deploy token from a GitHub secret instead of `flyctl auth login` locally and hoping it's
  cached on the runner?" (ephemeral runners, least-privilege, auditable secret rotation.)

## What this lab does not cover

- It does not run `flyctl` for real (no account in this sandbox) - the graded contract is static policy only,
  by design (see the spec header of this repo's real-infra labs).
- It does not manage multiple environments/regions, blue-green traffic shifting, or Fly Postgres - see
  "Stretch goals" for where to take it next.
