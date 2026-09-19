# Lab: Kubernetes Pod and Node Triage (kubectl JSON + a safe subprocess wrapper)

Parse `kubectl get pods/nodes -o json` output and answer the on-call questions: which pods are broken and *why*
(CrashLoopBackOff, ImagePullBackOff, OOMKilled, Pending because of insufficient CPU, Evicted, failing init
containers), how much CPU/memory does each namespace request and limit, what QoS class does each pod have, and
which nodes are NotReady or under pressure. You also write the small `Kubectl` wrapper that gets the JSON safely.

## Why it matters in a real job

Kubernetes troubleshooting is mostly reading structured status: `state` vs `lastState`, conditions, quantities in
five different notations. Being able to script it (for a Slack bot, a nightly report or a CI gate) is a very common
platform task, and the way you call `kubectl` from Python is a small security review in itself.

## Prerequisites (course chapters)

- [Linux, Docker and Kubernetes](../../systems/sf04-linux-docker-kubernetes.html)
- [Cloud and container ops by example](../../devops/do04-cloud-and-container-ops.html)
- [Config and data formats](../../devops/do02-config-yaml-json-toml.html) (JSON handling)
- [Automation scripts and resilience](../../devops/do03-automation-scripts-resilience.html) (subprocess, timeouts)

## Run it

```bash
cd labs/devops-k8s-triage
python -m venv .venv && source .venv/bin/activate    # optional but recommended
pip install -r requirements.txt
pytest -q                        # starter: every test fails until you implement it
LAB_TARGET=solution pytest -q    # maintainers / CI: the reference solution passes
```

No cluster, `kubectl` or network is needed: the tests read `tests/fixtures/pods.json` and `nodes.json`
(hand-built to match real `kubectl` output) and use a fake runner. **Never point the tests at a real cluster.**

## What is provided vs what you write

Provided: `models.py` (dataclasses and the problem-kind constants), the `KubectlError` class, the suffix tables in
`quantity.py`. You write: `quantity.py`, `pods.py`, `nodes.py`, `aggregate.py`, `kubectl.py`, `triage.py`.

## Tasks

1. **Quantities** - `parse_quantity` (exact `Decimal`), `cpu_to_millicores`, `memory_to_bytes`. Forms: `100m`, `1.5`, `2Gi`, `512Mi`, `1e3`, `129e6`, `129M`, plain integers. `Gi` is not `G`; `1E` is exa but `1E3` is 1000; `1K` is invalid; sub-millicore values round up.
2. **QoS** - Guaranteed / Burstable / BestEffort from `pod.spec` (compare parsed values, not strings; requests default to limits; init containers count).
3. **Effective resources** - per pod: `max(sum(containers), largest init container)`; count containers without limits.
4. **Diagnose pods** - one function, several problem kinds, using the fields kubectl really fills in (see the hints).
5. **Nodes** - `Ready=Unknown` is NotReady; only pressure conditions that are `"True"` count; cordoned is a flag, not a problem.
6. **Namespace totals** - skip Succeeded/Failed pods (they hold no resources).
7. **`Kubectl` wrapper** - argv list, `check=False`, timeout, no shell, stderr in the error, validate the namespace before running anything.
8. **Glue** - `build_report`, `triage_cluster`, `render_report`.

## Hints

<details><summary>Where each problem hides in the JSON</summary>

- CrashLoopBackOff: `status.containerStatuses[].state.waiting.reason`
- ImagePullBackOff / ErrImagePull: same place
- OOMKilled: `state.terminated.reason` **or** `lastState.terminated.reason` (a restarted container looks Running!)
- Pending, insufficient cpu: `status.conditions[]` with `type: PodScheduled`, `status: "False"`, `reason: Unschedulable`; the scheduler explains in `message`
- Evicted: `status.reason == "Evicted"` with `phase: Failed`
- Failing init container: `status.initContainerStatuses[]` (waiting CrashLoopBackOff, or terminated with non-zero `exitCode`)
</details>

<details><summary>Quantity regex</summary>

A number (`\d+\.?\d*` or `\.\d+`), then either an exponent `[eE][+-]?\d+` **or** one suffix from
`Ki Mi Gi Ti Pi Ei n u m k M G T P E`. Try the exponent alternative before the suffix so `1E3` is not "1 exa, then 3".
</details>

<details><summary>Why `Decimal`, and why round up</summary>

`0.1 + 0.2 != 0.3` with floats. Kubernetes rounds fractional millicores/bytes **up**, so `100u` is `1m`, not `0`.
</details>

<details><summary>Safe subprocess checklist</summary>

`subprocess.run(["kubectl", ...], capture_output=True, text=True, timeout=30, check=False)` - list not string,
never `shell=True`, always a timeout, look at `returncode` yourself, include `stderr` in the exception.
Reject user-supplied values that start with `-` so they cannot become flags.
</details>

## Stretch goals (reference only, not tested)

- Use the official Python client against a local **kind** cluster instead of shelling out:
  ```bash
  kind create cluster --name triage
  pip install kubernetes
  python - <<'PY'
  from kubernetes import client, config
  config.load_kube_config(context="kind-triage")
  for p in client.CoreV1Api().list_pod_for_all_namespaces().items:
      print(p.metadata.namespace, p.metadata.name, p.status.phase)
  PY
  ```
  Then create a pod with `image: nope/nope` and one with `resources.limits.memory: 10Mi` running a memory hog, and
  watch your triage report light up. Compare the client's typed objects (`p.status.container_statuses`) with the JSON you parse here.
- Add `kubectl top` data and flag pods using > 90% of their memory limit.
- Add node-level capacity: requested vs allocatable per node, and predict which pending pod fits where.
- Add `kubectl describe`-style event lookup for Pending pods.

## How this comes up in interviews

"A pod is stuck in Pending / CrashLoopBackOff - walk me through it" (the diagnosis steps above), "what is the
difference between requests and limits, and what QoS class results?" (and what gets evicted first), "why was my
container OOMKilled although the node has memory?" (cgroup limit, `lastState`), "how do you call kubectl from a
script safely?" (the wrapper), and the classic unit trap: `1Gi != 1G`.

## What this lab does not cover

- Fixtures are hand-built and abbreviated; real clusters add many fields (ownerReferences, managedFields, probes...).
- No live cluster interaction is graded; the `kubernetes` client and kind are a stretch goal only.
- No taints/tolerations, affinity, PodDisruptionBudgets, ephemeral containers, sidecar (restartable init) containers or
  multi-container OOM attribution beyond the first matching state.
- QoS is computed from `spec`; the API server's `status.qosClass` is the source of truth in a real cluster
  (the tests check both agree on the fixtures).
- Namespace totals ignore ResourceQuota/LimitRange defaults and pod overhead.
