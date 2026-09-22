"""Pick starter/ or solution/ from LAB_TARGET, expose the Dockerfile parsed for static policy checks,
and a REAL, session-scoped Docker container built and run from that target's assets/ - built with
`docker build`, started with `docker run`, and always stopped/removed (image too) at the end of the
session, even if a test fails or errors.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

TARGET = os.environ.get("LAB_TARGET", "starter")
LAB_DIR = Path(__file__).resolve().parent.parent
TARGET_DIR = LAB_DIR / TARGET
sys.path.insert(0, str(TARGET_DIR))
sys.dont_write_bytecode = True

import httpx  # noqa: E402
import pytest  # noqa: E402

from lab.dockerfile import parse_dockerfile  # noqa: E402
from lab.loader import DOCKERFILE, read_asset  # noqa: E402

ASSETS_DIR = TARGET_DIR / "assets"
# A random suffix means this tag can never collide with an image another process/agent on this same
# Docker daemon already built or is building, and we always know it's ours to remove afterwards.
IMAGE_TAG = f"mlops-real-container-deploy-{TARGET}-{uuid.uuid4().hex[:10]}:test"


@pytest.fixture
def dockerfile_text() -> str:
    return read_asset(DOCKERFILE, ASSETS_DIR)


@pytest.fixture
def dockerfile(dockerfile_text):
    return parse_dockerfile(dockerfile_text)


def assert_policy(problems: list[str]) -> None:
    """Fail with every violated rule listed, one per line."""
    assert not problems, "policy violations:\n  - " + "\n  - ".join(problems)


# --------------------------------------------------------------------------- real Docker helpers
def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _docker(*args: str, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)


def _wait_for_http(url: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(url, timeout=2)
            if resp.status_code == 200:
                return
        except httpx.HTTPError as exc:
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(
        f"{url} did not answer within {timeout}s (last error: {last_error!r}). If this is the "
        "starter image: check that the Dockerfile's CMD binds uvicorn to --host 0.0.0.0."
    )


@pytest.fixture(scope="session")
def live_server():
    """Build the REAL image from ``<LAB_TARGET>/assets`` with ``docker build``, run it with
    ``docker run``, wait for it to actually answer over HTTP, yield its details, then always stop
    the container (``--rm`` auto-removes it) and remove the image this session built.
    """
    build = _docker("build", "-t", IMAGE_TAG, str(ASSETS_DIR), timeout=900)
    if build.returncode != 0:
        pytest.fail(
            f"docker build failed for {TARGET}/assets (exit {build.returncode}):\n"
            f"{build.stdout[-4000:]}\n{build.stderr[-4000:]}"
        )

    port = _free_port()
    run = _docker("run", "-d", "--rm", "-p", f"127.0.0.1:{port}:8000", IMAGE_TAG, timeout=60)
    if run.returncode != 0:
        _docker("image", "rm", "-f", IMAGE_TAG)
        pytest.fail(f"docker run failed (exit {run.returncode}): {run.stderr}")
    container_id = run.stdout.strip()

    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_for_http(f"{base_url}/health", timeout=45)
        yield {"base_url": base_url, "container_id": container_id, "image_tag": IMAGE_TAG}
    finally:
        # Best-effort, resilient teardown: a slow/busy shared Docker daemon must never leave the
        # container or the image behind just because one cleanup step was briefly slow to respond.
        try:
            _docker("stop", "-t", "5", container_id, timeout=60)
        except subprocess.TimeoutExpired:
            try:
                _docker("kill", container_id, timeout=30)
            except subprocess.TimeoutExpired:
                pass
        # `--rm` removes the container asynchronously, so an immediate `image rm` can lose a race
        # against that in-flight removal ("image is being used by stopped container"). Retry a few
        # times with a short backoff instead of leaving the (multi-hundred-MB) image behind.
        for attempt in range(5):
            try:
                result = _docker("image", "rm", "-f", IMAGE_TAG, timeout=60)
            except subprocess.TimeoutExpired:
                result = None
            if result is not None and result.returncode == 0:
                break
            time.sleep(1)


def http_get(url: str) -> tuple[int, dict]:
    resp = httpx.get(url, timeout=5)
    return resp.status_code, resp.json()


def http_post(url: str, payload: dict) -> tuple[int, dict]:
    resp = httpx.post(url, json=payload, timeout=5)
    return resp.status_code, resp.json()
