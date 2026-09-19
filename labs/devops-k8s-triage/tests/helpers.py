from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def pod_doc(name="p", ns="default", containers=None, init=None, status=None) -> dict:
    """Minimal single-Pod document. ``containers``: list of resources dicts."""
    spec = {"containers": [{"name": f"c{i}", "image": "x", "resources": r} for i, r in enumerate(containers or [{}])]}
    if init:
        spec["initContainers"] = [{"name": f"i{i}", "image": "x", "resources": r} for i, r in enumerate(init)]
    return {"apiVersion": "v1", "kind": "Pod", "metadata": {"name": name, "namespace": ns},
            "spec": spec, "status": status or {"phase": "Running"}}


class FakeRunner:
    """Stands in for subprocess.run. ``replies`` maps a tuple of args (without the binary) to a result."""

    def __init__(self, replies=None, default=None):
        self.calls: list[tuple[list[str], dict]] = []
        self.replies = replies or {}
        self.default = default

    def __call__(self, cmd, **kwargs):
        self.calls.append((cmd, kwargs))
        reply = self.replies.get(tuple(cmd[1:]), self.default)
        if isinstance(reply, BaseException):
            raise reply
        if reply is None:
            raise AssertionError(f"unexpected command {cmd}")
        return reply


def ok(payload: dict) -> SimpleNamespace:
    return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")


def fail(code=1, stderr="") -> SimpleNamespace:
    return SimpleNamespace(returncode=code, stdout="", stderr=stderr)


def timeout_error() -> subprocess.TimeoutExpired:
    return subprocess.TimeoutExpired(cmd="kubectl", timeout=1)
