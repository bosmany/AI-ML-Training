"""A thin, safe wrapper around the ``kubectl`` binary with an injectable command runner."""
from __future__ import annotations

import subprocess
from collections.abc import Callable
from typing import Any

Runner = Callable[..., Any]  # subprocess.run-compatible: returns an object with .returncode/.stdout/.stderr


class KubectlError(RuntimeError):
    def __init__(self, message: str, *, cmd: list[str], returncode: int | None = None, stderr: str = "") -> None:
        super().__init__(message)
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr


class Kubectl:
    """Safe-subprocess pattern: argv is a LIST (never a shell string), there is ALWAYS a timeout,
    and failures surface stderr. Tests inject a fake ``runner`` - they never run real kubectl."""

    def __init__(self, runner: Runner = subprocess.run, *, binary: str = "kubectl",
                 timeout: float = 30.0, context: str | None = None) -> None:
        # TODO: store the arguments (the runner must default to subprocess.run and be stored as ``self._runner``).
        raise NotImplementedError

    def run_json(self, args: list[str]) -> dict[str, Any]:
        """Run ``[binary, (--context X), *args, "-o", "json"]`` through the runner and parse stdout.

        TODO: call ``runner(cmd, capture_output=True, text=True, timeout=..., check=False)``.
        - non-zero returncode -> KubectlError(message contains stderr, returncode=..., stderr=..., cmd=...)
        - subprocess.TimeoutExpired -> KubectlError mentioning "timed out"
        - FileNotFoundError -> KubectlError mentioning "not found"
        - invalid JSON on stdout -> KubectlError mentioning "JSON"
        """
        raise NotImplementedError

    def get_pods(self, namespace: str | None = None) -> dict[str, Any]:
        """``get pods --all-namespaces`` when ``namespace`` is None, else ``get pods -n <namespace>``.
        Validate the namespace BEFORE running anything: reject empty strings, anything starting with "-"
        (kubectl would parse it as a flag) and characters outside letters/digits/'-'/'.' -> ValueError."""
        raise NotImplementedError

    def get_nodes(self) -> dict[str, Any]:
        raise NotImplementedError
