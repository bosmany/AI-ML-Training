"""REAL Docker tests. Every test in this file depends on the ``live_server`` session fixture, which:

  1. runs ``docker build`` on ``<LAB_TARGET>/assets`` (a real image, not a mock),
  2. runs ``docker run`` to start a real container from it, mapped to a free host port,
  3. polls the real ``/health`` endpoint over real HTTP until the process answers,
  4. always stops the container and removes the image afterwards (see conftest.py).

If the starter's Dockerfile does not bind uvicorn to 0.0.0.0, step 3 times out and EVERY test below
fails with a clear message - that is intentional: you cannot test what you cannot reach.
"""

from __future__ import annotations

import subprocess
import time

from conftest import http_get, http_post

SETOSA = {"sepal_length": 5.1, "sepal_width": 3.5, "petal_length": 1.4, "petal_width": 0.2}
VIRGINICA = {"sepal_length": 6.5, "sepal_width": 3.0, "petal_length": 5.2, "petal_width": 2.0}
SPECIES = {"setosa", "versicolor", "virginica"}


def test_health_endpoint_reports_the_model_is_loaded(live_server):
    status, body = http_get(f"{live_server['base_url']}/health")
    assert status == 200
    assert body["status"] == "ok"
    assert body["model_loaded"] is True


def test_predict_returns_a_real_prediction_from_the_real_model(live_server):
    base_url = live_server["base_url"]

    status, body = http_post(f"{base_url}/predict", SETOSA)
    assert status == 200, f"predict failed for a textbook setosa sample: {body}"
    assert body["predicted_class"] in SPECIES
    assert body["predicted_class_index"] in {0, 1, 2}
    assert set(body["probabilities"]) == SPECIES
    assert abs(sum(body["probabilities"].values()) - 1.0) < 1e-6
    # These are the first row of the actual iris dataset (species 0) - a correctly trained model
    # must be confident about them, not just "return something".
    assert body["predicted_class"] == "setosa"

    status, body = http_post(f"{base_url}/predict", VIRGINICA)
    assert status == 200, f"predict failed for a textbook virginica sample: {body}"
    assert body["predicted_class"] == "virginica"


def test_predict_rejects_a_malformed_request_body(live_server):
    status, _ = http_post(f"{live_server['base_url']}/predict", {"sepal_length": 5.1})
    assert status == 422


def test_container_process_does_not_run_as_root(live_server):
    # `docker top` (with a custom -o format) is unsupported under this sandbox's daemon, so check the
    # real running user the same way an operator debugging a live container would: exec into it.
    top = subprocess.run(
        ["docker", "top", live_server["container_id"]],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert top.returncode == 0, top.stderr
    header, *rows = [line for line in top.stdout.splitlines() if line.strip()]
    uid_column = header.split().index("UID")
    users = [row.split()[uid_column] for row in rows]
    assert users, "docker top returned no processes for the running container"
    assert all(user not in {"root", "0"} for user in users), f"process(es) running as root: {users}"

    exec_result = subprocess.run(
        ["docker", "exec", live_server["container_id"], "id", "-u"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert exec_result.returncode == 0, exec_result.stderr
    assert exec_result.stdout.strip() != "0", "execing into the container defaults to root (uid 0)"


def test_docker_healthcheck_reports_the_container_healthy(live_server):
    """A real, live confirmation of the Dockerfile's own HEALTHCHECK - distinct from the static
    lint check, which only reads the instruction's text. Docker itself must run it and agree."""
    inspect = [
        "docker",
        "inspect",
        "--format",
        "{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck-configured{{end}}",
        live_server["container_id"],
    ]
    status = "unknown"
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        result = subprocess.run(inspect, capture_output=True, text=True, timeout=10)
        status = result.stdout.strip()
        if status == "healthy":
            break
        time.sleep(1)
    assert status == "healthy", f"container health status is {status!r} (expected 'healthy')"
