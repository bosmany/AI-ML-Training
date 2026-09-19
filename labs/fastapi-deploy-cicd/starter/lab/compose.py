"""Load a docker-compose file and find ``${VAR}`` references (compose interpolation syntax)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import yaml

from lab.errors import AssetError

_REF = re.compile(r"\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?:(?P<op>:?[-?+])(?P<arg>[^}]*))?\}")


@dataclass(frozen=True)
class EnvReference:
    name: str
    operator: str | None  # None, ":-", "-", ":?", "?", ":+", "+"
    argument: str | None

    @property
    def has_default(self) -> bool:
        return self.operator in (":-", "-")

    @property
    def is_required(self) -> bool:
        return self.operator in (":?", "?")


def find_env_references(value: str) -> list[EnvReference]:
    return [EnvReference(m["name"], m["op"], m["arg"]) for m in _REF.finditer(value)]


def load_compose(text: str) -> dict[str, Any]:
    """Parse the file and return the mapping; raises ``AssetError`` unless it defines ``services``."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise AssetError(f"docker-compose.yml is not valid YAML: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("services"), dict) or not data["services"]:
        raise AssetError("docker-compose.yml must define at least one entry under 'services:'")
    return data


def environment_of(service: dict[str, Any]) -> dict[str, str]:
    """Normalise ``environment:`` (mapping or ``KEY=value`` list) into a dict of strings."""
    env = service.get("environment") or {}
    if isinstance(env, list):
        pairs = (item.partition("=") for item in env)
        return {key: value for key, _, value in pairs}
    return {str(key): "" if value is None else str(value) for key, value in env.items()}
