#!/usr/bin/env python3
"""Verifier for broken/26-oomkilled-memory-limit.  Usage: python verify.py   (BROKEN_TARGET=solution for the reference)

Needs docker (no sudo) and python:3.12-alpine present locally (`docker pull python:3.12-alpine`; never pulled here).
Runs the compose job under a private project name, judges by `docker inspect` (OOMKilled / ExitCode / HostConfig)
and the job's output, and always removes the container and network afterwards.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
TARGET = HERE / ("solution" if os.environ.get("BROKEN_TARGET") == "solution" else "app")
IMAGE = "python:3.12-alpine"
MAX_LIMIT = 256 * 1024 * 1024        # the limit must stay, and stay sane (no "just give it 4g")
N_CHUNKS, CHUNK = 40, 3 * 1024 * 1024
checks = []


def check(name, ok, detail=""):
    checks.append({"name": name, "ok": bool(ok), "detail": detail})
    return bool(ok)


def finish():
    fixed = all(c["ok"] for c in checks) and bool(checks)
    score = 100 if fixed else min(99, round(100 * sum(c["ok"] for c in checks) / max(1, len(checks))))
    print(json.dumps({"fixed": fixed, "checks": checks, "score": score}, indent=2))
    sys.exit(0 if fixed else 1)


def sh(*args, timeout=60):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def expected_digest():
    h = hashlib.sha256()
    for i in range(N_CHUNKS):
        h.update(bytes([i % 256]) * CHUNK)
    return h.hexdigest()


def main():
    if shutil.which("docker") is None or sh("docker", "info", "--format", "{{.ServerVersion}}").returncode != 0:
        check("docker is available", False, "start docker; this scenario needs it")
        return finish()
    if sh("docker", "image", "inspect", IMAGE).returncode != 0:
        check(f"image {IMAGE} present locally", False, f"run: docker pull {IMAGE}")
        return finish()

    tmp = Path(tempfile.mkdtemp(prefix="broken26-"))
    proj = f"brk26{os.getpid()}"
    work = tmp / "proj"
    shutil.copytree(TARGET, work, ignore=shutil.ignore_patterns("__pycache__"))
    compose = ["docker", "compose", "-p", proj, "-f", str(work / "docker-compose.yml")]
    try:
        up = sh(*compose, "up", "-d", "--pull", "never", timeout=90)
        cid = sh(*compose, "ps", "-a", "-q", "report").stdout.strip()
        if up.returncode != 0 or not cid:
            check("docker compose up -d", False, (up.stderr or up.stdout)[-300:])
            return finish()
        sh("docker", "wait", cid, timeout=60)
        info = json.loads(sh("docker", "inspect", cid).stdout)[0]
        st, hc = info["State"], info["HostConfig"]
        logs = sh(*compose, "logs", "--no-color", "report").stdout

        check("job was not OOM-killed (State.OOMKilled false, exit code not 137)",
              not st["OOMKilled"] and st["ExitCode"] != 137,
              f"OOMKilled={st['OOMKilled']} ExitCode={st['ExitCode']}")
        check("job completed successfully (exit code 0)", st["ExitCode"] == 0 and not st["Running"],
              f"ExitCode={st['ExitCode']}")
        mem = hc["Memory"]
        check("a memory limit is still enforced and reasonable (0 < limit <= 256 MiB)",
              0 < mem <= MAX_LIMIT, f"HostConfig.Memory={mem}")
        check("OOM killer not disabled", not hc.get("OomKillDisable"), f"OomKillDisable={hc.get('OomKillDisable')}")

        line = next((l for l in logs.splitlines() if "DONE chunks=" in l), "")
        fields = dict(p.split("=", 1) for p in line.split() if "=" in p)
        check("output is correct: all 40 chunks fingerprinted (behaviour preserved)",
              fields.get("chunks") == str(N_CHUNKS) and fields.get("sha256") == expected_digest(),
              line[-140:] or "no DONE line")
        peak = int(fields.get("peak_rss_mb", "0") or 0)
        limit_mb = mem / (1024 * 1024)
        check("peak RSS leaves headroom: <= 90% of the limit",
              bool(mem) and 0 < peak <= 0.9 * limit_mb, f"peak_rss_mb={peak} limit_mb={limit_mb:.0f}")
    finally:
        sh(*compose, "down", "-v", "--remove-orphans", "-t", "1", timeout=90)
        shutil.rmtree(tmp, ignore_errors=True)
    finish()


if __name__ == "__main__":
    main()
