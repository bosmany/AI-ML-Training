"""Pick starter/ or solution/ from LAB_TARGET and expose parsed assets as fixtures."""

from __future__ import annotations

import os
import sys
from pathlib import Path

TARGET = os.environ.get("LAB_TARGET", "starter")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / TARGET))
sys.dont_write_bytecode = True

import pytest  # noqa: E402

from lab.compose import load_compose  # noqa: E402
from lab.dockerfile import parse_dockerfile  # noqa: E402
from lab.dockerignore import parse_dockerignore  # noqa: E402
from lab.loader import COMPOSE, DOCKERFILE, DOCKERIGNORE, WORKFLOW, read_asset  # noqa: E402
from lab.workflow import load_workflow  # noqa: E402


@pytest.fixture
def dockerfile_text() -> str:
    return read_asset(DOCKERFILE)


@pytest.fixture
def dockerfile(dockerfile_text):
    return parse_dockerfile(dockerfile_text)


@pytest.fixture
def ignore_patterns() -> list[str]:
    return parse_dockerignore(read_asset(DOCKERIGNORE))


@pytest.fixture
def compose():
    return load_compose(read_asset(COMPOSE))


@pytest.fixture
def workflow_text() -> str:
    return read_asset(WORKFLOW)


@pytest.fixture
def workflow(workflow_text):
    return load_workflow(workflow_text)


def assert_policy(problems: list[str]) -> None:
    """Fail with every violated rule listed, one per line."""
    assert not problems, "policy violations:\n  - " + "\n  - ".join(problems)
