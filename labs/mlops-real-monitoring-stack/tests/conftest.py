"""Session-scoped fixture that brings up the REAL docker-compose stack (app + Prometheus + Grafana),
waits for it to be healthy, hands the tests real URLs to hit, and tears everything down afterwards -
exactly once per test session, regardless of pass/fail, per the lab's "real infra" contract.

LAB_TARGET ("starter" default, or "solution") picks which lab/ package the app image is built from.
With the starter package every handler still raises NotImplementedError, so /health returns 500 and
this fixture's own health-wait loop times out and raises - which is exactly what makes every starter
test fail/error, without hanging: the timeout is bounded (60s) rather than infinite.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest
import requests

LAB_DIR = Path(__file__).resolve().parent.parent
COMPOSE_FILE = LAB_DIR / "docker-compose.yml"

APP_PORT = int(os.environ.get("APP_PORT", "18000"))
PROMETHEUS_PORT = int(os.environ.get("PROMETHEUS_PORT", "19090"))
GRAFANA_PORT = int(os.environ.get("GRAFANA_PORT", "13000"))

APP_URL = f"http://127.0.0.1:{APP_PORT}"
PROMETHEUS_URL = f"http://127.0.0.1:{PROMETHEUS_PORT}"
GRAFANA_URL = f"http://127.0.0.1:{GRAFANA_PORT}"


def _compose(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.setdefault("LAB_TARGET", os.environ.get("LAB_TARGET", "starter"))
    env.setdefault("APP_PORT", str(APP_PORT))
    env.setdefault("PROMETHEUS_PORT", str(PROMETHEUS_PORT))
    env.setdefault("GRAFANA_PORT", str(GRAFANA_PORT))
    return subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *args],
        cwd=LAB_DIR,
        env=env,
        check=check,
        capture_output=True,
        text=True,
        timeout=300,
    )


def wait_until(predicate, timeout: float, interval: float = 1.0, description: str = "condition"):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            if predicate():
                return
        except Exception as exc:  # noqa: BLE001 - keep polling, surface the last error on timeout
            last_error = exc
        time.sleep(interval)
    raise TimeoutError(f"timed out after {timeout}s waiting for: {description} (last error: {last_error})")


@pytest.fixture(scope="session")
def compose_stack():
    up = _compose("up", "-d", "--build", check=False)
    if up.returncode != 0:
        raise RuntimeError(f"docker compose up failed:\nSTDOUT:\n{up.stdout}\nSTDERR:\n{up.stderr}")
    try:
        def app_healthy() -> bool:
            return requests.get(f"{APP_URL}/health", timeout=10).status_code == 200

        wait_until(app_healthy, timeout=60, interval=1.5, description="app /health returns 200")

        def prometheus_ready() -> bool:
            return requests.get(f"{PROMETHEUS_URL}/-/ready", timeout=10).status_code == 200

        wait_until(prometheus_ready, timeout=30, interval=1.0, description="prometheus /-/ready")

        def target_up() -> bool:
            resp = requests.get(f"{PROMETHEUS_URL}/api/v1/targets", timeout=10).json()
            active = resp.get("data", {}).get("activeTargets", [])
            return any(t.get("labels", {}).get("job") == "fastapi-app" and t.get("health") == "up" for t in active)

        wait_until(target_up, timeout=30, interval=1.5, description="prometheus scrape target 'fastapi-app' is up")

        yield {"app": APP_URL, "prometheus": PROMETHEUS_URL, "grafana": GRAFANA_URL}
    finally:
        down = _compose("down", "-v", check=False)
        if down.returncode != 0:
            raise RuntimeError(f"docker compose down -v failed:\nSTDOUT:\n{down.stdout}\nSTDERR:\n{down.stderr}")
