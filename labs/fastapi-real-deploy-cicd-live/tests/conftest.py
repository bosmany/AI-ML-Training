"""Pick starter/ or solution/ from LAB_TARGET and expose parsed assets as fixtures."""

from __future__ import annotations

import os
import sys
from pathlib import Path

TARGET = os.environ.get("LAB_TARGET", "starter")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / TARGET))
sys.dont_write_bytecode = True

import pytest  # noqa: E402

from lab.flytoml import load_fly_toml  # noqa: E402
from lab.loader import FLY_TOML, WORKFLOW, read_asset  # noqa: E402
from lab.workflow import load_workflow  # noqa: E402


@pytest.fixture
def fly_toml_text() -> str:
    return read_asset(FLY_TOML)


@pytest.fixture
def fly_toml(fly_toml_text):
    return load_fly_toml(fly_toml_text)


@pytest.fixture
def workflow_text() -> str:
    return read_asset(WORKFLOW)


@pytest.fixture
def workflow(workflow_text):
    return load_workflow(workflow_text)


def assert_policy(problems: list[str]) -> None:
    """Fail with every violated rule listed, one per line."""
    assert not problems, "policy violations:\n  - " + "\n  - ".join(problems)
