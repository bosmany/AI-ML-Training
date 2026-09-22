# Lab: Config Auditor (PyYAML rule engine for docker-compose and Kubernetes)

Write a small policy linter for infrastructure YAML. It reads docker-compose and Kubernetes manifests (multi-document
files, anchors and JSON included), runs a set of rules (`:latest` images, missing limits and probes, privileged
containers, plaintext secrets, exposed ports) and reports every finding with its **file, JSON pointer and line**, as
text or JSON, with CI-friendly exit codes. This is the **guided tier** of the *Config Auditor* project: the YAML
loader with line numbers, the data model and the rule base class are provided; you write the rules, the engine, the
renderers and the CLI.

## Why it matters in a real job

Almost every platform team owns a "policy as code" gate: `conftest`, `kube-linter`, `checkov`, `trivy config` or a
home-grown script in CI. Writing one teaches you what those tools do underneath: parse safely, keep source locations,
model a rule as a pure function, tolerate hostile or odd input, let teams tune severities, and turn results into an
exit code a pipeline can act on.

## Prerequisites (course chapters)

- [Config and data formats](../../devops/do02-config-yaml-json-toml.html) (YAML, JSON, `safe_load`)
- [Files, errors and more](../../python/ch05-oop-files-errors.html) (classes, exceptions, files)
- [Professional Python](../../python/ch06-professional-python.html) (dataclasses, typing, tests)
- [Cloud and container ops by example](../../devops/do04-cloud-and-container-ops.html) (compose, Kubernetes basics)

## Run it

```bash
cd labs/devops-config-auditor
python -m venv .venv && source .venv/bin/activate    # optional but recommended
pip install -r requirements.txt
pytest -q                        # starter: every test fails until you implement it
LAB_TARGET=solution pytest -q    # maintainers / CI: the reference solution passes
```

Tests only read YAML fixtures in `tests/fixtures/` and temporary files: no Docker, cluster or network.
Try your finished tool on the fixtures (replace `starter` by `solution` to see the reference):

```bash
PYTHONPATH=starter python -c 'import sys; from lab.cli import main; sys.exit(main(sys.argv[1:]))' \
  tests/fixtures/compose_bad.yml --format json
echo "exit code: $?"
```

## What is provided vs what you write

Provided (read, do not edit): `models.py` (`Severity`, frozen `Finding`, `Document`, `ConfigParseError`), `loader.py`
(safe YAML loading + a JSON-pointer -> line index), `walk.py` (`iter_containers`: where each format keeps its containers),
`rule.py` (the `Rule` base class). You write, in `starter/lab/`: `rules.py`, `engine.py`, `report.py`, `cli.py`.

## Tasks

1. **Six rules** (`rules.py`) - `no-latest-tag`, `resource-limits`, `missing-probes`, `no-privileged`, `no-plaintext-secrets`, `no-exposed-ports`. Each docstring lists the true positives and the look-alikes that must **not** fire (a registry port is not a tag, a `valueFrom` secret is fine, a `Job` needs no probes, loopback ports are safe).
2. **Engine** (`engine.py`) - `run_rules` (disable, severity override, and a crashing rule becomes an *error*, never a silent pass), `audit_text` (parse errors become `file:line:col` errors, findings sorted), `collect_files`, `audit_paths` (one bad file does not stop the others).
3. **Config** (`parse_config`) - `rules: {<id>: {enabled: false, severity: high}}`, `yaml.safe_load` only, unknown rule ids are an error.
4. **Exit codes** (`Report.exit_code`) - `2` if anything could not be audited, `1` if a finding is at or above `--fail-on`, else `0`.
5. **Renderers** (`report.py`) - a pinned text format and a JSON document with a summary.
6. **CLI** (`cli.py`) - `auditor PATH... [--format text|json] [--fail-on low|medium|high|critical] [--config .auditor.yaml]`.

## Hints

<details><summary>Why <code>yaml.safe_load</code> and not <code>yaml.load</code></summary>

`yaml.load` with the full loader can construct arbitrary Python objects: `!!python/object/apply:os.system ["..."]`
runs a shell command while *parsing*. A linter that runs in CI on pull requests from strangers must never do that.
`SafeLoader` (used by the provided loader) only builds dicts, lists and scalars and raises an error for python tags.
</details>

<details><summary>Image tag parsing</summary>

Split off the last path segment first (`image.rsplit("/", 1)[-1]`), then look for `:` in it.
`registry.local:5000/app` has a colon but no tag; `nginx@sha256:...` is pinned by digest.
</details>

<details><summary>Compose port syntax</summary>

`"80"`, `"8080:80"`, `"127.0.0.1:8080:80"`, `"[::1]:8080:80"`, `"8080:80/udp"` and the long form
`{target: 80, published: 8080, host_ip: 127.0.0.1}` are all legal. With three colon-separated parts the first is the
host IP; without one, Docker binds `0.0.0.0`.
</details>

<details><summary>Why the engine catches exceptions from rules</summary>

A rule written by a colleague will meet a file nobody thought of (`image: 5`, `env: {}`). If it raises, the whole run
would crash and hide every other finding; if you swallowed it silently, CI would show a false green. Record it as an
error and let `exit_code` return 2.
</details>

<details><summary>Anchors and merge keys</summary>

`<<: *common` copies keys from an anchor. `SafeLoader` resolves this, so rules see the merged mapping, and the
provided line index points such keys at the line where the anchor defines them (a useful place to fix it).
</details>

## Stretch goals (not tested)

- Rule discovery through entry points so teams can add rules without editing the package.
- A `--baseline old.json` mode that reports only new findings, and a semantic `diff a.yaml b.yaml` that ignores key order and comments.
- SARIF 2.1.0 output and a GitHub Actions job that uploads it as code-scanning alerts.
- Rules for `runAsNonRoot`, `readOnlyRootFilesystem`, `hostNetwork`, and a Service of type `NodePort`.
- Run it on a real repository of manifests and count the false positives; tune a rule until you would trust it in CI.

## How this comes up in interviews

"How would you enforce that no manifest uses `:latest` or privileged containers?" (CI policy gate, admission
controller as the runtime backstop), "why is `yaml.load` dangerous?", "how do you keep a linter from blocking every
team on day one?" (severities, baselines, per-rule disable), "what should the exit code be when the tool itself
crashes?" (not 0), and "how do you avoid false positives?" (test look-alikes as carefully as true positives).

## What this lab does not cover

- Only the common shapes of compose and Kubernetes are understood (Pod, Deployment, StatefulSet, DaemonSet, ReplicaSet, Job, CronJob; no init containers, Helm templates or Kustomize overlays).
- Line numbers are those of keys/list items; flow-style YAML on one line shares one line number.
- No schema validation, no SARIF, no baseline or diff, no rule plugins, no parallelism for very large repositories.
- Secret detection is name-based: it will not find a key hidden in a `command` line or a high-entropy value under an innocent name.
