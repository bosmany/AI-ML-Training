"""Policy checks. Each ``check_*`` returns a list of human-readable problems (empty list = policy met).

The tests call these one by one, so a failing test names the exact rule you violated.
"""

from __future__ import annotations

import re
from typing import Any

from lab.flytoml import http_service_checks, vm_entries
from lab.workflow import Step, iter_steps, needed_jobs, parse_uses, trigger_names

SECRET_NAME = re.compile(r"(PASSWORD|PASSWD|SECRET|TOKEN|API_?KEY|PRIVATE_?KEY|CREDENTIAL)", re.IGNORECASE)
SECRET_VALUE_PATTERNS = {
    "GitHub token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"),
    "GitHub fine-grained token": re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    "AWS access key id": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "Slack token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    "Fly.io API token": re.compile(r"\bfm2_[A-Za-z0-9_+/=]{20,}"),
}

FLY_TOKEN_FROM_SECRET = re.compile(r"\$\{\{\s*secrets\.FLY_API_TOKEN\s*\}\}")


# =============================================================== fly.toml
def check_fly_app_name_set(fly: dict[str, Any]) -> list[str]:
    app = fly.get("app")
    if not app or not isinstance(app, str) or not app.strip():
        return ["fly.toml must set a top-level 'app = \"<unique-name>\"'"]
    if app != app.lower() or re.search(r"[^a-z0-9-]", app):
        return [f"app name '{app}' should use only lowercase letters, digits and hyphens (it becomes <app>.fly.dev)"]
    return []


def check_fly_primary_region_set(fly: dict[str, Any]) -> list[str]:
    region = fly.get("primary_region")
    if not region or not isinstance(region, str):
        return ["fly.toml should set 'primary_region' so the machine is placed deliberately, not wherever flyctl defaults"]
    return []


def check_fly_http_service_config(fly: dict[str, Any]) -> list[str]:
    svc = fly.get("http_service")
    if not isinstance(svc, dict):
        return ["fly.toml must define an [http_service] section describing how the app is reached"]
    problems = []
    if not isinstance(svc.get("internal_port"), int):
        problems.append("[http_service] must set 'internal_port' (the port your app listens on inside the machine)")
    if svc.get("force_https") is not True:
        problems.append("[http_service] should set force_https = true so plain HTTP is redirected")
    return problems


def check_fly_healthcheck_configured(fly: dict[str, Any]) -> list[str]:
    checks = http_service_checks(fly)
    if not checks:
        return ["[http_service] must define at least one [[http_service.checks]] block that probes /health"]
    problems = []
    for check in checks:
        if not isinstance(check, dict):
            problems.append("each http_service.checks entry must be a table (grace_period/interval/timeout/method/path)")
            continue
        if "/health" not in str(check.get("path", "")):
            problems.append("the health check 'path' must call the app's /health endpoint")
        if "method" in check and str(check["method"]).upper() != "GET":
            problems.append("the health check 'method' should be GET")
        for key in ("interval", "timeout", "grace_period"):
            if key not in check:
                problems.append(f"health check is missing '{key}' (Fly needs it to decide when a machine is unhealthy)")
    return problems


def check_fly_vm_resources_declared(fly: dict[str, Any]) -> list[str]:
    entries = vm_entries(fly)
    if not entries:
        return ["fly.toml should declare [[vm]] with a 'size' so the machine spec is explicit, not left to flyctl's default"]
    return [f"[[vm]] entry {i} has no 'size'" for i, entry in enumerate(entries) if not entry.get("size")]


def check_fly_toml_has_no_baked_secrets(fly: dict[str, Any], raw_text: str) -> list[str]:
    problems = []
    env = fly.get("env") or {}
    for key, value in env.items():
        if SECRET_NAME.search(str(key)) and str(value).strip():
            problems.append(
                f"[env] {key} is a literal value baked into fly.toml - secrets belong in "
                "`flyctl secrets set` (or the GitHub Actions secret store), never in a committed [env] table"
            )
    for label, pattern in SECRET_VALUE_PATTERNS.items():
        if pattern.search(raw_text):
            problems.append(f"fly.toml contains what looks like a real {label}")
    return problems


# =============================================================== deploy.yml: triggers / permissions / pinning
def check_workflow_triggers(workflow: dict[str, Any]) -> list[str]:
    events = trigger_names(workflow)
    problems = []
    if "push" not in events:
        problems.append("the deploy workflow must trigger on 'push' (a deploy happens after code lands on main)")
    triggers = workflow.get("on")
    if isinstance(triggers, dict):
        push = triggers.get("push")
        branches = (push or {}).get("branches") if isinstance(push, dict) else None
        if not branches or list(branches) != ["main"]:
            problems.append(
                "the push trigger must be restricted to `branches: [main]` - otherwise every branch push "
                "deploys to production"
            )
    for forbidden in ("pull_request", "pull_request_target"):
        if forbidden in events:
            problems.append(
                f"do not trigger the deploy workflow on '{forbidden}': a pull request (possibly from a fork) "
                "would run with access to FLY_API_TOKEN and deploy untrusted code"
            )
    return problems


def check_workflow_permissions(workflow: dict[str, Any]) -> list[str]:
    top = workflow.get("permissions")
    if top is None:
        return ["set a top-level 'permissions:' (e.g. contents: read); the default token may be read-write"]
    if isinstance(top, str):
        if top not in {"read-all", "none"}:
            return [f"top-level permissions '{top}' is too broad for a workflow that only checks out code and deploys"]
        return []
    problems = []
    if top.get("contents") != "read":
        problems.append("top-level permissions should include 'contents: read' so checkout still works")
    for scope, level in top.items():
        if level == "write":
            problems.append(f"top-level permission {scope}: write is unnecessary - this workflow never writes to the repo")
    return problems


_SHA = re.compile(r"^[0-9a-f]{40}$")
_VERSION_TAG = re.compile(r"^v?\d+(\.\d+){0,2}$")


def check_actions_pinned(workflow: dict[str, Any]) -> list[str]:
    problems = []
    for step in iter_steps(workflow):
        if not step.uses or step.uses.startswith(("./", "docker://")):
            continue
        name, ref = parse_uses(step.uses)
        if ref is None:
            problems.append(f"{step.job}: '{step.uses}' has no @version")
        elif not (_SHA.match(ref) or _VERSION_TAG.match(ref)):
            problems.append(f"{step.job}: '{step.uses}' pins to '{ref}' (a moving branch); use a version tag or a commit SHA")
    return problems


def check_job_timeouts(workflow: dict[str, Any]) -> list[str]:
    return [
        f"job '{job_id}' has no timeout-minutes (a hung deploy burns runner minutes for 6 hours by default)"
        for job_id, job in workflow["jobs"].items()
        if not isinstance(job.get("timeout-minutes"), int)
    ]


def check_no_literal_secrets_in_workflow(workflow: dict[str, Any], raw_text: str) -> list[str]:
    problems = []
    for label, pattern in SECRET_VALUE_PATTERNS.items():
        if pattern.search(raw_text):
            problems.append(f"the workflow contains what looks like a real {label}")
    scopes: list[tuple[str, dict[str, Any]]] = [("workflow env", workflow.get("env") or {})]
    for job_id, job in workflow["jobs"].items():
        scopes.append((f"{job_id} env", job.get("env") or {}))
    for step in iter_steps(workflow):
        scopes.append((f"{step.job} step {step.index} with", step.with_))
        scopes.append((f"{step.job} step {step.index} env", step.env))
    for where, mapping in scopes:
        for key, value in mapping.items():
            if SECRET_NAME.search(str(key)) and not re.search(r"\$\{\{\s*(secrets\.\w+|github\.token)\s*\}\}", str(value)):
                problems.append(f"{where}: '{key}' must come from ${{{{ secrets.NAME }}}}, not a literal ({value!r})")
    return problems


# =============================================================== deploy.yml: deploy / health-check / rollback
def _is_test_step(step: Step) -> bool:
    return bool(re.search(r"\bpytest\b", step.run))


def _is_deploy_step(step: Step) -> bool:
    if step.uses and parse_uses(step.uses)[0].startswith("superfly/flyctl-actions"):
        return True
    return bool(re.search(r"\bflyctl\s+deploy\b", step.run))


def _is_health_check_step(step: Step) -> bool:
    return bool(re.search(r"\b(curl|httpx|requests|wget)\b", step.run)) and "/health" in step.run


def _is_rollback_step(step: Step) -> bool:
    return bool(re.search(r"flyctl\s+releases\s+rollback", step.run))


def check_deploy_runs_only_after_tests_pass(workflow: dict[str, Any]) -> list[str]:
    steps = list(iter_steps(workflow))
    test_steps = [s for s in steps if _is_test_step(s)]
    deploy_steps = [s for s in steps if _is_deploy_step(s)]
    if not test_steps:
        return ["no step runs pytest before deploying"]
    if not deploy_steps:
        return ["no step runs 'flyctl deploy' (or the superfly/flyctl-actions setup + deploy)"]
    problems = []
    for deploy in deploy_steps:
        same_job_before = any(t.job == deploy.job and t.index < deploy.index for t in test_steps)
        via_needs = any(t.job in needed_jobs(workflow, deploy.job) for t in test_steps)
        if not (same_job_before or via_needs):
            problems.append(
                f"job '{deploy.job}' can deploy without the tests having passed first "
                "(put tests in their own job and add 'needs: <test job>' to the deploy job)"
            )
    return problems


def check_fly_token_comes_from_secret(workflow: dict[str, Any]) -> list[str]:
    problems = []
    found = False
    for step in iter_steps(workflow):
        for where, mapping in (("env", step.env), ("with", step.with_)):
            value = mapping.get("FLY_API_TOKEN")
            if value is None:
                continue
            found = True
            if not FLY_TOKEN_FROM_SECRET.search(str(value)):
                problems.append(
                    f"{step.job} step {step.index} {where}.FLY_API_TOKEN must read "
                    f"'${{{{ secrets.FLY_API_TOKEN }}}}', not {value!r}"
                )
    if not found:
        problems.append("no step sets FLY_API_TOKEN from secrets.FLY_API_TOKEN - flyctl needs it to authenticate")
    return problems


def check_health_check_runs_after_deploy(workflow: dict[str, Any]) -> list[str]:
    steps = list(iter_steps(workflow))
    deploy_steps = [s for s in steps if _is_deploy_step(s)]
    health_steps = [s for s in steps if _is_health_check_step(s)]
    if not deploy_steps:
        return ["no 'flyctl deploy' step found"]
    if not health_steps:
        return ["no step verifies the deployed app's /health endpoint after deploying"]
    problems = []
    for deploy in deploy_steps:
        after = [h for h in health_steps if h.job == deploy.job and h.index > deploy.index]
        if not after:
            problems.append(f"job '{deploy.job}': the health-check step must run AFTER 'flyctl deploy', in the same job")
    if health_steps and not any(re.search(r"--retry|sleep|for\s+\w+\s+in", h.run) for h in health_steps):
        problems.append(
            "the health-check step should retry for a few seconds (e.g. `curl --retry N --retry-delay N`) - a "
            "machine that is still booting is not the same as a failed deploy"
        )
    return problems


def check_rollback_on_deploy_failure(workflow: dict[str, Any]) -> list[str]:
    steps = list(iter_steps(workflow))
    deploy_steps = [s for s in steps if _is_deploy_step(s)]
    rollback_steps = [s for s in steps if _is_rollback_step(s)]
    if not rollback_steps:
        return ["no step rolls back the release ('flyctl releases rollback') when the deploy or health-check fails"]
    problems = []
    for rb in rollback_steps:
        if "failure()" not in rb.if_:
            problems.append(
                f"job '{rb.job}' step {rb.index}: the rollback step must be gated on 'if: failure()' so it only "
                "runs when the deploy or the health-check actually failed"
            )
        same_job_deploy_before = any(d.job == rb.job and d.index < rb.index for d in deploy_steps)
        if not same_job_deploy_before:
            problems.append(f"job '{rb.job}' step {rb.index}: the rollback step must come after the deploy step in the same job")
    return problems


# =============================================================== cross-file consistency
def check_health_check_targets_fly_app(fly: dict[str, Any], workflow: dict[str, Any]) -> list[str]:
    app = fly.get("app")
    if not app:
        return []  # already reported by check_fly_app_name_set
    health_steps = [s for s in iter_steps(workflow) if _is_health_check_step(s)]
    if not health_steps:
        return []  # already reported by check_health_check_runs_after_deploy
    host = f"{app}.fly.dev"
    if not any(host in step.run for step in health_steps):
        return [f"the health-check step must probe the app declared in fly.toml (expected host '{host}')"]
    return []
