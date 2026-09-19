"""Load a GitHub Actions workflow and walk its steps."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import yaml

from lab.errors import AssetError


def load_workflow(text: str) -> dict[str, Any]:
    """Parse the workflow; raises ``AssetError`` unless it has ``jobs``.

    Gotcha: YAML 1.1 (PyYAML) reads the bare key ``on`` as the boolean ``True``. We move it back to
    the string key ``"on"`` so the rest of the code can use ``workflow["on"]``.
    """
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise AssetError(f"workflow is not valid YAML: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), dict) or not data["jobs"]:
        raise AssetError("workflow must define at least one job under 'jobs:'")
    if True in data and "on" not in data:
        data["on"] = data.pop(True)
    return data


def trigger_names(workflow: dict[str, Any]) -> set[str]:
    """Event names that trigger the workflow, whichever of the 3 YAML shapes was used."""
    triggers = workflow.get("on")
    if isinstance(triggers, str):
        return {triggers}
    if isinstance(triggers, list):
        return {str(item) for item in triggers}
    if isinstance(triggers, dict):
        return {str(key) for key in triggers}
    return set()


@dataclass(frozen=True)
class Step:
    job: str
    index: int
    data: dict[str, Any]

    @property
    def uses(self) -> str | None:
        return self.data.get("uses")

    @property
    def run(self) -> str:
        return str(self.data.get("run", ""))

    @property
    def with_(self) -> dict[str, Any]:
        return self.data.get("with") or {}

    @property
    def env(self) -> dict[str, Any]:
        return self.data.get("env") or {}


def iter_steps(workflow: dict[str, Any]) -> Iterator[Step]:
    for job_id, job in workflow["jobs"].items():
        for index, step in enumerate(job.get("steps") or []):
            yield Step(job_id, index, step)


def parse_uses(uses: str) -> tuple[str, str | None]:
    """``actions/checkout@v4`` -> ``("actions/checkout", "v4")``; no ``@`` -> ``(name, None)``."""
    name, _, ref = uses.partition("@")
    return name, (ref or None)
