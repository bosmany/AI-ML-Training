# Broken-System Labs

Real engineers spend more time diagnosing systems that are already broken than building new ones. Each lab here
is a small, runnable system with **one seeded fault**. You get the symptoms (never the cause), find the root
cause, fix it, prove the fix, and write a short blameless postmortem. The 50 scenarios are catalogued in
[`catalog.json`](catalog.json) and browsable at [`index.html`](index.html) (filters, search, a hint ladder and an
attempt tracker). Ten are runnable today; the rest are planned.

## How a lab works

```
broken/<NN>-<slug>/
  README.md               symptoms only (no cause), what you have, your job
  app/                    the broken system (Python 3.12, stdlib + sqlite + pytest). Edit this.
  app/tests/              existing behaviour tests; they must stay green
  verify.py               exit 0 only when the fault is really fixed AND behaviour is preserved
  hints.json              3 hints: L1 nudge (-10), L2 pointer to the signal (-20), L3 near-solution (-30)
  solution/               the fixed version + ROOT_CAUSE.md (cause, why the symptoms, prevention). Spoilers!
  postmortem_template.md  blameless postmortem: impact, timeline, root cause, 5 whys, action items
```

The loop: **observe** (README symptoms, run the demo/load tool) -> **hypothesise** -> **confirm** with a
measurement -> **fix** in `app/` -> **verify** -> **write up** in `postmortem.md` -> **prevent** (add a regression test).
Do not open `solution/` until you have a verified fix of your own.

## Commands

Use the course virtualenv (needs Python 3.11+ and `pytest`; `make bootstrap` sets it up).

```bash
make broken ID=01                        # verify your app/ for scenario 01 and show your score
make broken ID=01 HINTS=1,2 MINUTES=35   # self-report hints used and minutes spent
BROKEN_TARGET=solution make broken ID=01 # verify the reference solution instead of your app/
make broken-check                        # maintainers: every lab must FAIL on app/ and PASS on solution/
python broken/_dev/mutation_check.py     # maintainers: wrong fixes must still fail (spoilers)
```

Direct use, without make: `python broken/run.py 01` or `cd broken/01-memory-leak && python verify.py`
(`verify.py` prints a JSON result `{fixed, checks, score}` and exits 0 only when everything passes).

## Scoring

`score = 100 - hints - time penalty + prevention bonus`

| Item | Points |
| --- | --- |
| Hint L1 (nudge) / L2 (pointer to the signal) / L3 (near-solution) | -10 / -20 / -30 |
| Time penalty | -1 per 3 minutes after the first 20, capped at -20 |
| Prevention action | +10 for a passing `app/tests/test_regression_*.py`, or a filled `prevent`/`detect` action item in `postmortem.md` |

**Success** requires all three: (a) `verify.py` passes (the fault is fixed), (b) no collateral regression
(the existing behaviour tests stay green; `verify.py` runs them), and (c) `postmortem.md` has a real
"Root cause" section (copy `postmortem_template.md` to `postmortem.md` and fill it in). A fix without a written
root cause is reported as incomplete. Hints and minutes are self-reported (the page at `index.html` tracks
your attempts in this browser); the point is honest practice, not a leaderboard.

## Rules every lab follows

Hermetic and deterministic; no network; under 60 seconds; no stray files (temp dirs only); no sleep longer
than 2 seconds; the verifier fails on the untouched `app/` and passes on `solution/`; at least two plausible
wrong fixes (band-aids) still fail the verifier.

## The 50 scenarios

| ID | Title | Category | Difficulty (1-5) | Status |
| --- | --- | --- | --- | --- |
| [01-memory-leak](01-memory-leak/README.md) | Memory leak | Application | 2 | available |
| [02-regex-cpu](02-regex-cpu/README.md) | One input pins the CPU | Application | 3 | available |
| 03-deadlock | Requests hang forever | Application | 4 | planned |
| [04-double-charge](04-double-charge/README.md) | Double charge | Application | 3 | available |
| [05-pool-exhaustion](05-pool-exhaustion/README.md) | Timeouts under load | Application | 3 | available |
| [06-n-plus-one](06-n-plus-one/README.md) | The slow orders endpoint | Application | 2 | available |
| 07-blocked-event-loop | The API stalls | Application | 3 | planned |
| 08-retry-storm | The outage that made itself worse | Application | 4 | planned |
| 09-dst-bug | Reports off by an hour | Application | 3 | planned |
| 10-swallowed-error | Jobs silently missing | Application | 3 | planned |
| [11-missing-index](11-missing-index/README.md) | The 30-second query | Database | 2 | available |
| [12-long-transaction](12-long-transaction/README.md) | Writes stall | Database | 4 | available |
| 13-replica-lag | Users see stale data | Database | 3 | planned |
| 14-wal-disk-full | Database down: no space left | Database | 4 | planned |
| 15-migration-lock | Deploy freezes the app | Database | 4 | planned |
| 16-update-order-deadlock | Random deadlocks | Database | 4 | planned |
| 17-max-connections | Too many connections | Database | 3 | planned |
| 18-untested-backup | The backup that could not restore | Database | 3 | planned |
| 19-dns-ttl | Some users hit the old host | Network | 3 | planned |
| 20-mtu | Large uploads fail | Network | 4 | planned |
| 21-expired-tls-cert | Everything is red at 09:00 | Network | 2 | planned |
| 22-security-group-change | Service unreachable after a tidy-up | Network | 2 | planned |
| 23-lb-health-flapping | Intermittent 502s | Network | 3 | planned |
| 24-clock-skew | Auth fails on one node | Network | 3 | planned |
| [25-crashloop-bad-env](25-crashloop-bad-env/README.md) | CrashLoopBackOff | Kubernetes & containers | 2 | available |
| [26-oomkilled-memory-limit](26-oomkilled-memory-limit/README.md) | OOMKilled | Kubernetes & containers | 3 | available |
| 27-imagepullbackoff | ImagePullBackOff | Kubernetes & containers | 1 | planned |
| 28-pending-pods | Pods stuck in Pending | Kubernetes & containers | 2 | planned |
| 29-bad-rollout | Bad rollout takes traffic | Kubernetes & containers | 3 | planned |
| 30-liveness-kills-slow-starter | Liveness kills the slow starter | Kubernetes & containers | 3 | planned |
| 31-hpa-thrash | HPA thrash | Kubernetes & containers | 4 | planned |
| 32-data-lost-on-drain | Data lost on node drain | Kubernetes & containers | 3 | planned |
| [33-flaky-order-dependence](33-flaky-order-dependence/README.md) | Flaky tests | CI/CD | 3 | available |
| 34-stale-cache | Old code deployed | CI/CD | 3 | planned |
| 35-secret-in-git-history | Secret in git history | CI/CD | 3 | planned |
| 36-no-rollback | The bad release that stayed | CI/CD | 3 | planned |
| 37-unpinned-dependency | Build broke, code did not change | CI/CD | 2 | planned |
| 38-slow-docker-builds | Slow Docker builds | CI/CD | 2 | planned |
| 39-public-bucket | Public bucket | Cloud & cost | 2 | planned |
| 40-bill-spike | The bill doubled | Cloud & cost | 3 | planned |
| 41-rate-limited-429 | 429 Too Many Requests | Cloud & cost | 2 | planned |
| 42-terraform-state-drift | Terraform state lock and drift | Cloud & cost | 3 | planned |
| 43-asg-flapping | Auto Scaling flaps | Cloud & cost | 3 | planned |
| 44-region-outage-no-failover | Region outage, no failover | Cloud & cost | 4 | planned |
| 45-sql-injection | SQL injection | Security, observability & ML | 2 | planned |
| 46-ssrf-url-fetcher | SSRF in the URL fetcher | Security, observability & ML | 4 | planned |
| 47-no-correlation-ids | Cannot trace a request | Security, observability & ML | 2 | planned |
| 48-alert-fatigue | Alert fatigue | Security, observability & ML | 3 | planned |
| 49-data-drift | The model quietly got worse | Security, observability & ML | 4 | planned |
| 50-train-serve-skew | Great offline, poor online | Security, observability & ML | 4 | planned |
