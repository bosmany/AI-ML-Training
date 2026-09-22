#!/usr/bin/env python3
"""Verifier for broken/25-crashloop-bad-env.  Usage: python verify.py   (BROKEN_TARGET=solution for the reference)

Needs docker (works without sudo) and the image python:3.12-alpine present locally (`docker pull python:3.12-alpine`;
this is the only thing that ever touches the network, and the verifier never pulls). It starts your compose file
under a private project name, judges the result through `docker inspect`, and always tears everything down.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
TARGET = HERE / ("solution" if os.environ.get("BROKEN_TARGET") == "solution" else "app")
IMAGE = "python:3.12-alpine"
checks = []


def check(name, ok, detail=""):
    checks.append({"name": name, "ok": bool(ok), "detail": detail})
    return bool(ok)


def finish():
    fixed = all(c["ok"] for c in checks) and bool(checks)
    score = 100 if fixed else min(99, round(100 * sum(c["ok"] for c in checks) / max(1, len(checks))))
    print(json.dumps({"fixed": fixed, "checks": checks, "score": score}, indent=2))
    sys.exit(0 if fixed else 1)


def sh(*args, cwd=None, env=None, timeout=60):
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)


def inspect(cid):
    out = sh("docker", "inspect", cid).stdout
    return json.loads(out)[0]


def main():
    if shutil.which("docker") is None or sh("docker", "info", "--format", "{{.ServerVersion}}").returncode != 0:
        check("docker is available", False, "start docker; this scenario needs it")
        return finish()
    if sh("docker", "image", "inspect", IMAGE).returncode != 0:
        check(f"image {IMAGE} present locally", False, f"run: docker pull {IMAGE}")
        return finish()

    tmp = Path(tempfile.mkdtemp(prefix="broken25-"))
    proj = f"brk25{os.getpid()}"
    work = tmp / "proj"
    shutil.copytree(TARGET, work, ignore=shutil.ignore_patterns("__pycache__"))
    compose = ["docker", "compose", "-p", proj, "-f", str(work / "docker-compose.yml")]
    try:
        # --- fail-fast validation must survive (a band-aid that swallows bad config is not a fix)
        base = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        good = sh(sys.executable, str(work / "service" / "main.py"), "--check", env=dict(base, WORKERS="4"))
        bad = sh(sys.executable, str(work / "service" / "main.py"), "--check", env=dict(base, WORKERS="four"))
        check("service still rejects an invalid WORKERS value (fail fast preserved)",
              good.returncode == 0 and bad.returncode != 0 and "WORKERS" in bad.stderr,
              f"good rc={good.returncode}, bad rc={bad.returncode}")

        up = sh(*compose, "up", "-d", "--pull", "never", timeout=90)
        if up.returncode != 0:
            check("docker compose up -d", False, (up.stderr or up.stdout)[-300:])
            return finish()
        cid = sh(*compose, "ps", "-q", "web").stdout.strip()
        state = {}
        deadline = time.time() + 20
        while time.time() < deadline:
            state = inspect(cid)
            st = state["State"]
            if state["RestartCount"] >= 2:
                break                                   # crash loop confirmed
            if st.get("Health", {}).get("Status") == "healthy":
                time.sleep(2)                           # must STAY up
                state = inspect(cid)
                break
            time.sleep(0.5)
        st = state["State"]
        rc = state["RestartCount"]
        health = st.get("Health", {}).get("Status")
        check("service is running and healthy, with no restarts",
              st["Running"] and not st["Restarting"] and rc == 0 and health == "healthy",
              f"status={st['Status']} exit={st['ExitCode']} restarts={rc} health={health}")
        logs = sh(*compose, "logs", "--no-color", "web").stdout
        check("service logged 'ready workers=<n>' (the real app is running)",
              "ready workers=" in logs and "config error" not in logs, logs.strip().splitlines()[-1][:120] if logs.strip() else "no logs")
        env = dict(e.split("=", 1) for e in state["Config"]["Env"] if "=" in e)
        w = env.get("WORKERS", "")
        check("effective WORKERS env var is an integer in 1..16",
              w.isdigit() and 1 <= int(w) <= 16, f"WORKERS={w!r}")
        policy = state["HostConfig"]["RestartPolicy"]["Name"]
        check("restart policy kept (fix the cause, do not disable supervision)",
              policy in ("unless-stopped", "always", "on-failure"), f"policy={policy!r}")
    finally:
        sh(*compose, "down", "-v", "--remove-orphans", "-t", "1", timeout=90)
        shutil.rmtree(tmp, ignore_errors=True)
    finish()


if __name__ == "__main__":
    main()
