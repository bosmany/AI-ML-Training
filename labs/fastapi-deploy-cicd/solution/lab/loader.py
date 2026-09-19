"""Locate and read the learner-authored files (``<target>/assets``)."""

from __future__ import annotations

from pathlib import Path

from lab.errors import AssetError

# .../<target>/lab/loader.py -> .../<target>/assets   (target is "starter" or "solution")
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

DOCKERFILE = "Dockerfile"
DOCKERIGNORE = ".dockerignore"
COMPOSE = "docker-compose.yml"
WORKFLOW = ".github/workflows/ci.yml"


def read_asset(relative_path: str, assets_dir: Path | None = None) -> str:
    """Return the text of ``assets/<relative_path>`` or raise ``AssetError`` explaining what is wrong."""
    path = (assets_dir or ASSETS_DIR) / relative_path
    if not path.is_file():
        raise AssetError(f"assets/{relative_path} does not exist - create it")
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise AssetError(f"assets/{relative_path} is empty - write it")
    return text
