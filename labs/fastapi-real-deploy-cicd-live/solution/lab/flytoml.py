"""Load and inspect a ``fly.toml`` (Fly.io app configuration).

Fly.io only ever *reads* this file (flyctl writes it once via ``flyctl launch``), so parsing with the
standard-library ``tomllib`` (read-only, Python 3.11+) is enough - no extra dependency needed.
"""

from __future__ import annotations

import tomllib
from typing import Any

from lab.errors import AssetError


def load_fly_toml(text: str) -> dict[str, Any]:
    """Parse the file; raises ``AssetError`` unless it is valid TOML that names an ``app``."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise AssetError(f"fly.toml is not valid TOML: {exc}") from exc
    if not isinstance(data, dict) or not data.get("app"):
        raise AssetError("fly.toml must set a top-level 'app = \"<name>\"'")
    return data


def http_service_checks(fly: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalise ``[http_service.checks]`` (a table) or ``[[http_service.checks]]`` (an array of tables)."""
    checks = (fly.get("http_service") or {}).get("checks")
    if not checks:
        return []
    return checks if isinstance(checks, list) else [checks]


def vm_entries(fly: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalise ``[vm]`` / ``[[vm]]`` into a list."""
    vm = fly.get("vm")
    if not vm:
        return []
    return vm if isinstance(vm, list) else [vm]
