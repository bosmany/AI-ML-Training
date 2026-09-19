"""Policy checks. Each ``check_*`` returns a list of human-readable problems (empty list = policy met).

The tests call these one by one, so a failing test names the exact rule you violated.
"""

from __future__ import annotations

import re
from typing import Any

from lab.compose import environment_of, find_env_references
from lab.dockerfile import Dockerfile, split_image
from lab.dockerignore import is_ignored
from lab.workflow import Step, iter_steps, parse_uses, trigger_names

SECRET_NAME = re.compile(r"(PASSWORD|PASSWD|SECRET|TOKEN|API_?KEY|PRIVATE_?KEY|CREDENTIAL)", re.IGNORECASE)
SECRET_VALUE_PATTERNS = {
    "GitHub token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"),
    "GitHub fine-grained token": re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    "AWS access key id": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "Slack token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    "Docker Hub token": re.compile(r"\bdckr_pat_[A-Za-z0-9_-]{10,}"),
}


def _version_of(image_tag: str | None) -> tuple[int, int] | None:
    match = re.match(r"(\d+)\.(\d+)", image_tag or "")
    return (int(match[1]), int(match[2])) if match else None


# =============================================================== Dockerfile
def check_multi_stage(df: Dockerfile) -> list[str]:
    problems = []
    if len(df.stages) < 2:
        return ["only one FROM: use a multi-stage build (a 'builder' stage, then a slim runtime stage)"]
    aliases = {s.alias for s in df.stages if s.alias}
    copies = [i for i in df.final.of("COPY") if "from" in i.flags()]
    if not any(i.flags()["from"] in aliases or i.flags()["from"].isdigit() for i in copies):
        problems.append("the final stage never does 'COPY --from=<earlier stage> ...' so the extra stage is unused")
    return problems


def check_pinned_base_images(df: Dockerfile) -> list[str]:
    problems = []
    seen_aliases: set[str] = set()
    for stage in df.stages:
        base = stage.base
        if base not in seen_aliases and base != "scratch":
            name, tag, digest = split_image(base)
            if "$" in base:
                problems.append(f"FROM {base}: cannot resolve the variable - give the ARG a default value")
            elif digest:
                pass  # pinned by digest is the strongest pin
            elif tag is None:
                problems.append(f"FROM {base}: no tag means ':latest'. Pin a version, e.g. python:3.12-slim-bookworm")
            elif tag.lower() == "latest":
                problems.append(f"FROM {base}: never use ':latest' - builds must be reproducible")
            elif _version_of(tag) is None:
                problems.append(f"FROM {base}: tag '{tag}' does not start with a version number like 3.12")
        if stage.alias:
            seen_aliases.add(stage.alias)
    return problems


def check_non_root_user(df: Dockerfile) -> list[str]:
    users = df.final.of("USER")
    if not users:
        return ["the final stage has no USER instruction, so the app runs as root"]
    last = users[-1].args.strip().split(":")[0].strip()
    if last in {"root", "0"}:
        return [f"the last USER in the final stage is '{last}' - switch to an unprivileged user"]
    return []


def check_healthcheck(df: Dockerfile) -> list[str]:
    checks = df.final.of("HEALTHCHECK")
    if not checks:
        return ["the final stage has no HEALTHCHECK instruction"]
    check = checks[-1]
    if check.args.strip().upper() == "NONE":
        return ["HEALTHCHECK NONE disables the check"]
    problems = []
    if "CMD" not in check.args:
        problems.append("HEALTHCHECK needs a CMD")
    if "/health" not in check.args:
        problems.append("the HEALTHCHECK command should call the app's /health endpoint")
    if "interval" not in check.flags() or "timeout" not in check.flags():
        problems.append("set --interval and --timeout on the HEALTHCHECK explicitly")
    return problems


def check_no_baked_secrets(df: Dockerfile, raw_text: str) -> list[str]:
    problems = []
    for ins in df.all_instructions():
        if ins.keyword in {"ENV", "ARG"}:
            for key, value in re.findall(r"([A-Za-z_][A-Za-z0-9_]*)=(\"[^\"]*\"|'[^']*'|\S+)", ins.args) or [
                (ins.args.split()[0], " ".join(ins.args.split()[1:])) if ins.args.split() else ("", "")
            ]:
                value = value.strip("\"'")
                if SECRET_NAME.search(key) and value and not value.startswith("$"):
                    problems.append(f"line {ins.line}: {ins.keyword} {key} has a literal value baked into the image")
        if ins.keyword in {"COPY", "ADD"}:
            sources = [t for t in ins.args.split()[:-1] if not t.startswith("--")]
            for source in sources:
                base = source.rsplit("/", 1)[-1]
                if base == ".env" or base.startswith(".env.") and base != ".env.example" or base.endswith((".pem", ".key")):
                    problems.append(f"line {ins.line}: {ins.keyword} {source} copies a secret file into the image")
    for label, pattern in SECRET_VALUE_PATTERNS.items():
        if pattern.search(raw_text):
            problems.append(f"the Dockerfile contains what looks like a {label}")
    return problems


def check_cache_friendly_layer_order(df: Dockerfile) -> list[str]:
    for stage in df.stages:
        instructions = stage.instructions
        installs = [n for n, i in enumerate(instructions) if i.keyword == "RUN" and re.search(r"pip3? install", i.args)]
        if not installs:
            continue
        install_at = installs[0]
        before = instructions[:install_at]
        local_copies = [i for i in before if i.keyword in {"COPY", "ADD"} and "from" not in i.flags()]
        requirements_first = [i for i in local_copies if "requirements" in i.args]
        source_copies = [i for i in local_copies if "requirements" not in i.args]
        problems = []
        if not requirements_first:
            problems.append("copy requirements.txt BEFORE the 'pip install' RUN so the dependency layer is cached")
        if source_copies:
            problems.append(
                f"line {source_copies[0].line}: application source is copied before 'pip install' - every code "
                "edit would re-install all dependencies. Copy requirements first, install, THEN copy the source"
            )
        return problems
    return ["no 'RUN pip install ...' found in any stage"]


def check_pip_no_cache(df: Dockerfile) -> list[str]:
    env_ok = any(
        re.search(r"PIP_NO_CACHE_DIR=(1|true|on|yes)", i.args, re.IGNORECASE) for i in df.all_instructions() if i.keyword == "ENV"
    )
    problems = []
    for ins in df.all_instructions():
        if ins.keyword == "RUN" and re.search(r"pip3? install", ins.args) and "--no-cache-dir" not in ins.args and not env_ok:
            problems.append(f"line {ins.line}: pip install without --no-cache-dir (or PIP_NO_CACHE_DIR=1) bloats the image")
    return problems


def check_exec_form_command(df: Dockerfile) -> list[str]:
    starts = df.final.of("CMD") + df.final.of("ENTRYPOINT")
    if not starts:
        return ["the final stage has no CMD/ENTRYPOINT"]
    problems = []
    for ins in starts:
        if not ins.is_exec_form:
            problems.append(
                f"line {ins.line}: {ins.keyword} uses shell form; use the JSON exec form so the app is PID 1 and "
                "receives SIGTERM"
            )
    return problems


def check_python_runtime_env(df: Dockerfile) -> list[str]:
    text = " ".join(i.args for i in df.final.of("ENV"))
    return [
        f"the final stage should ENV {name}=1"
        for name in ("PYTHONUNBUFFERED", "PYTHONDONTWRITEBYTECODE")
        if not re.search(rf"{name}[= ]\"?1", text)
    ]


def check_exposed_port_and_bind_address(df: Dockerfile) -> list[str]:
    problems = []
    if not df.final.of("EXPOSE"):
        problems.append("no EXPOSE instruction (document the port the app listens on)")
    command = [t for i in df.final.of("CMD") + df.final.of("ENTRYPOINT") for t in (i.exec_args() or i.args.split())]
    joined = " ".join(command)
    if "uvicorn" not in joined:
        problems.append("the start command should run uvicorn")
    elif "0.0.0.0" not in joined:
        problems.append("uvicorn defaults to 127.0.0.1 which is unreachable from outside the container: add --host 0.0.0.0")
    return problems


# =============================================================== .dockerignore
REQUIRED_IGNORES = {
    ".git": [".git", ".git/HEAD"],
    ".env": [".env"],
    ".env.* variants": [".env.local", ".env.production"],
    "virtualenvs": [".venv/bin/python", "venv/bin/python"],
    "bytecode caches": ["app/__pycache__/main.cpython-312.pyc"],
}


def check_dockerignore_has_sensible_entries(patterns: list[str]) -> list[str]:
    problems = []
    for label, samples in REQUIRED_IGNORES.items():
        if not any(is_ignored(patterns, sample) for sample in samples):
            problems.append(f".dockerignore does not exclude {label} (e.g. {samples[0]})")
    return problems


def check_dockerignore_keeps_build_inputs(patterns: list[str]) -> list[str]:
    needed = ["requirements.txt", "app/main.py", "app/__init__.py"]
    return [f".dockerignore excludes '{path}' which the image build needs" for path in needed if is_ignored(patterns, path)]


# =============================================================== docker-compose.yml
def _services(compose: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {name: (svc or {}) for name, svc in compose["services"].items()}


def check_compose_builds_api_from_dockerfile(compose: dict[str, Any]) -> list[str]:
    api = _services(compose).get("api")
    if api is None:
        return ["compose must define a service named 'api'"]
    build = api.get("build")
    if not build:
        return ["service 'api' needs a 'build:' section (context '.') so `docker compose up --build` uses your Dockerfile"]
    context = build if isinstance(build, str) else build.get("context")
    if context not in {".", "./"}:
        return [f"service 'api' build context is {context!r}; expected '.' (the folder holding the Dockerfile)"]
    return []


def check_compose_healthchecks(compose: dict[str, Any]) -> list[str]:
    problems = []
    services = _services(compose)
    if len(services) < 2:
        problems.append("expected at least two services: 'api' plus a dependency such as 'db'")
    for name, svc in services.items():
        hc = svc.get("healthcheck")
        if not hc or hc.get("disable"):
            problems.append(f"service '{name}' has no healthcheck")
            continue
        for key in ("test", "interval", "timeout", "retries"):
            if key not in hc:
                problems.append(f"service '{name}' healthcheck is missing '{key}'")
    return problems


def check_compose_depends_on_healthy(compose: dict[str, Any]) -> list[str]:
    services = _services(compose)
    api = services.get("api")
    if api is None:
        return ["compose must define a service named 'api'"]
    depends = api.get("depends_on")
    if not isinstance(depends, dict) or not depends:
        return ["'api' must use the long form depends_on: {db: {condition: service_healthy}} (the list form only "
                "waits for the container to START, not to be READY)"]
    problems = []
    for dep, config in depends.items():
        if dep not in services:
            problems.append(f"depends_on refers to unknown service '{dep}'")
        elif (config or {}).get("condition") != "service_healthy":
            problems.append(f"depends_on.{dep}.condition must be service_healthy")
    return problems


def check_compose_secrets_via_variables(compose: dict[str, Any]) -> list[str]:
    problems = []
    for name, svc in _services(compose).items():
        for key, value in environment_of(svc).items():
            refs = find_env_references(value)
            if SECRET_NAME.search(key):
                if not refs:
                    problems.append(f"{name}.environment.{key} is a literal; use ${{{key}}} taken from the environment/.env")
                elif any(r.has_default for r in refs):
                    problems.append(f"{name}.environment.{key} has a default value; a secret must be required (${{VAR:?message}})")
            match = re.search(r"://[^/\s:@]+:([^@\s]+)@", value)
            if match and "${" not in match.group(1):
                problems.append(f"{name}.environment.{key} embeds a literal password in a URL")
    return problems


def check_compose_images_pinned(compose: dict[str, Any]) -> list[str]:
    problems = []
    for name, svc in _services(compose).items():
        image = svc.get("image")
        if image is None:
            if not svc.get("build"):
                problems.append(f"service '{name}' has neither image nor build")
            continue
        if svc.get("build"):
            continue  # our own image: tag comes from a variable like ${IMAGE_TAG:-dev}
        _, tag, digest = split_image(image)
        if not digest and (tag is None or tag == "latest" or _version_of(tag) is None):
            problems.append(f"service '{name}' image '{image}' must be pinned to a version tag (not latest / untagged)")
    return problems


def check_compose_restart_policy(compose: dict[str, Any]) -> list[str]:
    return [
        f"service '{name}' has no restart policy (unless-stopped / on-failure / always)"
        for name, svc in _services(compose).items()
        if svc.get("restart") not in {"unless-stopped", "on-failure", "always"}
        and not str(svc.get("restart", "")).startswith("on-failure")
    ]


def check_compose_port_from_variable(compose: dict[str, Any]) -> list[str]:
    api = _services(compose).get("api")
    if api is None:
        return ["compose must define a service named 'api'"]
    ports = api.get("ports") or []
    if not ports:
        return ["'api' must publish a port"]
    if not any("${" in str(p) and str(p).endswith(":8000") for p in ports):
        return ["publish the API port with a variable host port, e.g. \"${API_PORT:-8000}:8000\", so two stacks can coexist"]
    return []


# =============================================================== GitHub Actions
def check_workflow_triggers(workflow: dict[str, Any]) -> list[str]:
    events = trigger_names(workflow)
    problems = [f"workflow must trigger on '{e}'" for e in ("push", "pull_request") if e not in events]
    if "pull_request_target" in events:
        problems.append("pull_request_target runs with secrets on fork code - do not use it for CI")
    return problems


WRITE_ALLOWED_SCOPES = {"packages", "id-token", "attestations", "security-events"}


def check_workflow_permissions(workflow: dict[str, Any]) -> list[str]:
    problems = []
    top = workflow.get("permissions")
    if top is None:
        return ["set a top-level 'permissions:' (e.g. contents: read); the default token may be read-write"]
    if isinstance(top, str):
        if top not in {"read-all", "none"} and top != "{}":
            problems.append(f"top-level permissions '{top}' is too broad")
    else:
        for scope, level in top.items():
            if level == "write":
                problems.append(f"top-level permission {scope}: write - grant write only on the single job that needs it")
    if isinstance(top, dict) and top.get("contents") != "read":
        problems.append("top-level permissions should include 'contents: read' so checkout works")
    for job_id, job in workflow["jobs"].items():
        perms = job.get("permissions")
        if isinstance(perms, str):
            if perms == "write-all":
                problems.append(f"job '{job_id}' uses write-all")
        elif isinstance(perms, dict):
            for scope, level in perms.items():
                if level == "write" and scope not in WRITE_ALLOWED_SCOPES:
                    problems.append(f"job '{job_id}' grants {scope}: write, which a CI job never needs")
    return problems


_SHA = re.compile(r"^[0-9a-f]{40}$")
_VERSION_TAG = re.compile(r"^v\d+(\.\d+){0,2}$")


def check_actions_pinned(workflow: dict[str, Any]) -> list[str]:
    problems = []
    for step in iter_steps(workflow):
        if not step.uses or step.uses.startswith(("./", "docker://")):
            continue
        name, ref = parse_uses(step.uses)
        if ref is None:
            problems.append(f"{step.job}: '{step.uses}' has no @version")
        elif not (_SHA.match(ref) or _VERSION_TAG.match(ref)):
            problems.append(f"{step.job}: '{step.uses}' pins to '{ref}' (a moving branch); use a version tag like @v4 or a commit SHA")
    return problems


def _is_test_step(step: Step) -> bool:
    return bool(re.search(r"\bpytest\b", step.run))


def _is_build_step(step: Step) -> bool:
    if step.uses and parse_uses(step.uses)[0] == "docker/build-push-action":
        return True
    return bool(re.search(r"docker(?: compose)? build|docker buildx build", step.run))


def _needed_jobs(workflow: dict[str, Any], job_id: str) -> set[str]:
    found: set[str] = set()
    pending = [job_id]
    while pending:
        needs = workflow["jobs"][pending.pop()].get("needs") or []
        for dep in [needs] if isinstance(needs, str) else needs:
            if dep not in found and dep in workflow["jobs"]:
                found.add(dep)
                pending.append(dep)
    return found


def check_tests_run_before_image_build(workflow: dict[str, Any]) -> list[str]:
    steps = list(iter_steps(workflow))
    test_steps = [s for s in steps if _is_test_step(s)]
    build_steps = [s for s in steps if _is_build_step(s)]
    if not test_steps:
        return ["no step runs pytest"]
    if not build_steps:
        return ["no step builds the Docker image (docker/build-push-action or `docker build`)"]
    problems = []
    for build in build_steps:
        same_job_before = any(t.job == build.job and t.index < build.index for t in test_steps)
        via_needs = any(t.job in _needed_jobs(workflow, build.job) for t in test_steps)
        if not (same_job_before or via_needs):
            problems.append(
                f"job '{build.job}' builds the image without pytest having passed first "
                "(put tests in their own job and add 'needs: <test job>' to the build job)"
            )
    return problems


def check_pip_cache(workflow: dict[str, Any]) -> list[str]:
    for step in iter_steps(workflow):
        if step.uses and parse_uses(step.uses)[0] == "actions/setup-python" and step.with_.get("cache") == "pip":
            return []
        if step.uses and parse_uses(step.uses)[0] == "actions/cache" and "pip" in str(step.with_.get("path", "")):
            return []
    return ["pip downloads are not cached: use actions/setup-python with 'cache: pip' (or actions/cache on ~/.cache/pip)"]


def check_no_literal_secrets_in_workflow(workflow: dict[str, Any], raw_text: str) -> list[str]:
    problems = []
    for label, pattern in SECRET_VALUE_PATTERNS.items():
        if pattern.search(raw_text):
            problems.append(f"the workflow contains what looks like a {label}")
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


def check_job_timeouts(workflow: dict[str, Any]) -> list[str]:
    return [
        f"job '{job_id}' has no timeout-minutes (a hung job burns runner minutes for 6 hours by default)"
        for job_id, job in workflow["jobs"].items()
        if not isinstance(job.get("timeout-minutes"), int)
    ]


def check_push_is_guarded(workflow: dict[str, Any]) -> list[str]:
    problems = []
    for step in iter_steps(workflow):
        if not (step.uses and parse_uses(step.uses)[0] == "docker/build-push-action"):
            continue
        push = step.with_.get("push", False)
        guard_text = str(step.data.get("if", "")) + str(push)
        literally_pushes = push is True or (isinstance(push, str) and push.strip().lower() == "true")
        expression = isinstance(push, str) and "github." in push
        if literally_pushes and "github." not in str(step.data.get("if", "")):
            problems.append(f"{step.job}: the image is pushed unconditionally, including from pull requests")
        elif push and not literally_pushes and not expression and "github." not in guard_text:
            problems.append(f"{step.job}: unrecognised push condition {push!r}")
    return problems


# =============================================================== cross-file consistency
def check_python_versions_match(df: Dockerfile, workflow: dict[str, Any]) -> list[str]:
    _, tag, _ = split_image(df.final.base)
    image_version = _version_of(tag)
    ci_versions = []
    for step in iter_steps(workflow):
        if step.uses and parse_uses(step.uses)[0] == "actions/setup-python":
            ci_versions.append(_version_of(str(step.with_.get("python-version", ""))))
    if image_version is None:
        return ["cannot read the Python version from the final FROM tag"]
    if not ci_versions:
        return ["the workflow never calls actions/setup-python with a python-version"]
    return [
        f"CI tests on Python {v[0]}.{v[1]} but the image runs {image_version[0]}.{image_version[1]}"
        for v in ci_versions
        if v != image_version
    ]


def check_health_path_and_port_agree(df: Dockerfile, compose: dict[str, Any]) -> list[str]:
    problems = []
    exposed = {p for i in df.final.of("EXPOSE") for p in i.args.split()}
    api = _services(compose).get("api", {})
    targets = {str(p).rsplit(":", 1)[-1].split("/")[0] for p in api.get("ports") or []}
    if exposed and targets and not (exposed & targets):
        problems.append(f"Dockerfile EXPOSEs {sorted(exposed)} but compose publishes container port(s) {sorted(targets)}")
    test = (api.get("healthcheck") or {}).get("test")
    text = " ".join(test) if isinstance(test, list) else str(test or "")
    if "/health" not in text:
        problems.append("the compose healthcheck for 'api' should call /health like the Dockerfile HEALTHCHECK")
    return problems
