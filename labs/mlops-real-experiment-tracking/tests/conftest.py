"""Starts one REAL `mlflow server` subprocess for the whole test session, on a free port, with a
real sqlite backend store and a real local artifact root - not the no-op default MLflow client, and
not a mock. Every test in this lab talks to this live HTTP server."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

TARGET = os.environ.get("LAB_TARGET", "starter")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / TARGET))
sys.dont_write_bytecode = True

import pytest  # noqa: E402
import requests  # noqa: E402


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_until_up(url: str, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            resp = requests.get(url, timeout=1)
            if resp.status_code == 200:
                return
        except requests.RequestException as exc:  # server not accepting connections yet
            last_error = exc
        time.sleep(0.3)
    raise RuntimeError(f"mlflow server never became healthy at {url}: {last_error}")


@pytest.fixture(scope="session")
def mlflow_tracking_uri(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Start a real ``mlflow server`` (sqlite backend, local artifact root) and yield its URL."""
    root = tmp_path_factory.mktemp("mlflow_server")
    backend_db = root / "backend.db"
    artifact_root = root / "artifacts"
    artifact_root.mkdir()
    log_path = root / "server.log"
    port = _free_port()
    tracking_uri = f"http://127.0.0.1:{port}"

    cmd = [
        sys.executable,
        "-m",
        "mlflow",
        "server",
        "--backend-store-uri",
        f"sqlite:///{backend_db}",
        "--default-artifact-root",
        str(artifact_root),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    with open(log_path, "wb") as log_file:
        process = subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT)

    try:
        _wait_until_up(f"{tracking_uri}/health")
    except RuntimeError:
        process.terminate()
        process.wait(timeout=10)
        server_log = log_path.read_text(errors="replace") if log_path.exists() else "<no log>"
        raise RuntimeError(f"mlflow server failed to start; log:\n{server_log}")

    yield tracking_uri

    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


@pytest.fixture
def experiment_name() -> str:
    """A fresh experiment name per test so tests never see each other's runs."""
    return f"exp-{uuid.uuid4().hex[:10]}"


@pytest.fixture
def model_name() -> str:
    """A fresh registered-model name per test so tests never share registry versions."""
    return f"model-{uuid.uuid4().hex[:10]}"
