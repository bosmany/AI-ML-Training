"""Pick which implementation the tests import as ``lab``, and stand up (or skip) a real
LocalStack container for the session.

Learners run ``pytest`` (target = starter). Maintainers/CI run ``LAB_TARGET=solution pytest``.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.dont_write_bytecode = True

_TARGET = os.environ.get("LAB_TARGET", "starter")
_LAB_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_LAB_DIR / _TARGET))

import pytest  # noqa: E402  (after sys.path setup)

LOCALSTACK_IMAGE = "localstack/localstack:3.8.1"  # pinned: the "latest" tag now requires a
# LOCALSTACK_AUTH_TOKEN license even for S3/IAM/Lambda; 3.8.1 predates that and is fully free.
REQUIRED_SERVICES = ("s3", "iam", "lambda", "sts")
HANDLER_PATH = _LAB_DIR / "terraform" / "lambda_src" / "handler.py"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_health(endpoint: str, timeout: float = 180.0) -> None:
    deadline = time.monotonic() + timeout
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{endpoint}/_localstack/health", timeout=3) as resp:
                data = json.loads(resp.read())
            services = data.get("services", {})
            if all(services.get(name) == "available" for name in REQUIRED_SERVICES):
                return
        except (urllib.error.URLError, ConnectionError, OSError, ValueError) as exc:
            last_err = exc
        time.sleep(1)
    raise RuntimeError(f"LocalStack did not become healthy within {timeout}s: {last_err}")


@pytest.fixture(scope="session")
def localstack_endpoint():
    """Start one real LocalStack container for the whole test session and tear it down after.

    Only actually started when ``LAB_TARGET=solution``: every starter function raises
    ``NotImplementedError`` before it ever makes a network call, so paying for a real ~5-15s
    container startup on every starter run (which must fail regardless) would be wasted time.
    Skips cleanly with a clear reason if docker is missing or the container fails to start -
    never silently falls back to a fake.
    """
    if _TARGET != "solution":
        yield "http://127.0.0.1:1"  # unreachable on purpose; starter code must never reach it
        return

    if shutil.which("docker") is None:
        pytest.skip("docker binary not found on PATH: cannot start a real LocalStack container")

    name = f"tf-localstack-lab-{uuid.uuid4().hex[:10]}"
    port = _free_port()
    run_cmd = [
        "docker", "run", "-d", "--name", name,
        "-p", f"{port}:4566",
        "-e", "SERVICES=" + ",".join(REQUIRED_SERVICES) + ",logs",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        LOCALSTACK_IMAGE,
    ]
    try:
        subprocess.run(run_cmd, check=True, capture_output=True, text=True, timeout=120)
    except FileNotFoundError:
        pytest.skip("docker binary not found on PATH")
    except subprocess.CalledProcessError as exc:
        pytest.skip(f"could not start a real LocalStack container: {exc.stderr.strip()}")

    endpoint = f"http://127.0.0.1:{port}"
    try:
        _wait_for_health(endpoint)
        yield endpoint
    finally:
        # LocalStack's Lambda provider launches one extra sibling container per function
        # (named "<this container's name>-lambda-<function>-<hash>") via the mounted docker
        # socket. A graceful `docker stop` (SIGTERM) gives LocalStack's own shutdown hooks a
        # chance to remove those; only fall back to `docker rm -f` (which skips that hook
        # entirely) if it does not exit in time. Either way, sweep for and remove any sibling
        # containers left behind, so a killed/crashed run cannot leak them.
        stopped = subprocess.run(
            ["docker", "stop", "--time", "10", name], capture_output=True, text=True, timeout=30
        )
        if stopped.returncode != 0:
            subprocess.run(["docker", "kill", name], capture_output=True, text=True, timeout=15)
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True, timeout=30)

        leftover = subprocess.run(
            ["docker", "ps", "-aq", "--filter", f"name=^{name}-"],
            capture_output=True, text=True, timeout=15,
        )
        ids = leftover.stdout.split()
        if ids:
            subprocess.run(["docker", "rm", "-f", *ids], capture_output=True, text=True, timeout=30)


@pytest.fixture
def cfg(localstack_endpoint):
    """A ``StackConfig`` with unique resource names per test, so tests sharing one LocalStack
    container never collide with each other."""
    from lab.models import StackConfig

    suffix = uuid.uuid4().hex[:8]
    return StackConfig(
        endpoint_url=localstack_endpoint,
        handler_path=HANDLER_PATH,
        bucket_name=f"tf-demo-bucket-{suffix}",
        role_name=f"tf-demo-role-{suffix}",
        policy_name=f"tf-demo-policy-{suffix}",
        function_name=f"tf-demo-fn-{suffix}",
    )


@pytest.fixture
def local_cfg():
    """A ``StackConfig`` that does NOT depend on a real running container - for tests that only
    construct clients or build a zip and never make a network call."""
    from lab.models import StackConfig

    return StackConfig(
        endpoint_url="http://127.0.0.1:4566",
        handler_path=HANDLER_PATH,
        bucket_name="tf-demo-bucket-unit",
        role_name="tf-demo-role-unit",
        policy_name="tf-demo-policy-unit",
        function_name="tf-demo-fn-unit",
    )
