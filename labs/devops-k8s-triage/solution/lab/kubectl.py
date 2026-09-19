"""A thin, safe wrapper around the ``kubectl`` binary with an injectable command runner."""
from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from typing import Any

Runner = Callable[..., Any]  # subprocess.run-compatible: returns .returncode/.stdout/.stderr


class KubectlError(RuntimeError):
    def __init__(self, message: str, *, cmd: list[str], returncode: int | None = None, stderr: str = "") -> None:
        super().__init__(message)
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr


class Kubectl:
    """Never uses a shell: the command is a LIST, there is always a timeout, and failures carry stderr."""

    def __init__(self, runner: Runner = subprocess.run, *, binary: str = "kubectl",
                 timeout: float = 30.0, context: str | None = None) -> None:
        self._runner = runner
        self._binary = binary
        self._timeout = timeout
        self._context = context

    def _build(self, args: list[str]) -> list[str]:
        cmd = [self._binary]
        if self._context:
            cmd += ["--context", self._context]
        return cmd + args

    def run_json(self, args: list[str]) -> dict[str, Any]:
        cmd = self._build(args + ["-o", "json"])
        try:
            proc = self._runner(cmd, capture_output=True, text=True, timeout=self._timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise KubectlError(f"kubectl timed out after {self._timeout}s", cmd=cmd) from exc
        except FileNotFoundError as exc:
            raise KubectlError(f"{self._binary} not found on PATH", cmd=cmd) from exc
        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            raise KubectlError(f"kubectl exited {proc.returncode}: {stderr}", cmd=cmd,
                               returncode=proc.returncode, stderr=stderr)
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise KubectlError(f"kubectl printed invalid JSON: {exc}", cmd=cmd, returncode=0) from exc

    def get_pods(self, namespace: str | None = None) -> dict[str, Any]:
        """All namespaces when ``namespace`` is None."""
        if namespace is None:
            return self.run_json(["get", "pods", "--all-namespaces"])
        _check_name(namespace)
        return self.run_json(["get", "pods", "-n", namespace])

    def get_nodes(self) -> dict[str, Any]:
        return self.run_json(["get", "nodes"])


def _check_name(value: str) -> None:
    """Refuse values that kubectl would parse as a flag (argument injection) or that are not DNS labels."""
    if not value or value.startswith("-") or not all(c.isalnum() or c in "-." for c in value):
        raise ValueError(f"invalid Kubernetes name: {value!r}")
