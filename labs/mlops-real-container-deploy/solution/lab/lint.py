"""Static Dockerfile policy checks. Each ``check_*`` returns a list of human-readable problems
(empty list = policy met). The tests call these one by one, so a failing test names the exact rule
you violated. These rules are hermetic (no Docker needed); the live behaviour they protect (a
container that a stranger can actually reach and that runs as an unprivileged user) is separately
proven for real in ``tests/test_live_container.py``.
"""

from __future__ import annotations

import re

from lab.dockerfile import Dockerfile, split_image

SECRET_NAME = re.compile(r"(PASSWORD|PASSWD|SECRET|TOKEN|API_?KEY|PRIVATE_?KEY|CREDENTIAL)", re.IGNORECASE)
SECRET_VALUE_PATTERNS = {
    "GitHub token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"),
    "AWS access key id": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}


def _version_of(image_tag: str | None) -> tuple[int, int] | None:
    match = re.match(r"(\d+)\.(\d+)", image_tag or "")
    return (int(match[1]), int(match[2])) if match else None


def check_multi_stage(df: Dockerfile) -> list[str]:
    if len(df.stages) < 2:
        return ["only one FROM: use a multi-stage build (a 'builder' stage that trains the model, then a slim "
                "runtime stage that only ships the artifact and the app)"]
    aliases = {s.alias for s in df.stages if s.alias}
    copies = [i for i in df.final.of("COPY") if "from" in i.flags()]
    if not any(i.flags()["from"] in aliases or i.flags()["from"].isdigit() for i in copies):
        return ["the final stage never does 'COPY --from=<earlier stage> ...' so the extra stage is unused"]
    return []


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
        return ["the final stage has no USER instruction, so the model server runs as root"]
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
                f"line {source_copies[0].line}: application/training source is copied before 'pip install' - every "
                "code edit would re-install all dependencies. Copy requirements first, install, THEN copy the source"
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
                f"line {ins.line}: {ins.keyword} uses shell form; use the JSON exec form so uvicorn is PID 1 and "
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
        problems.append("no EXPOSE instruction (document the port the model server listens on)")
    command = [t for i in df.final.of("CMD") + df.final.of("ENTRYPOINT") for t in (i.exec_args() or i.args.split())]
    joined = " ".join(command)
    if "uvicorn" not in joined:
        problems.append("the start command should run uvicorn")
    elif "0.0.0.0" not in joined:
        problems.append(
            "uvicorn defaults to 127.0.0.1 which is unreachable from outside the container (and from the host "
            "via 'docker run -p'): add --host 0.0.0.0"
        )
    return problems
