"""Pick which implementation the tests import as ``lab``.

Learners run ``pytest`` (target = starter). Maintainers/CI run ``LAB_TARGET=solution pytest``.
"""
import os
import sys
from pathlib import Path

import pytest

sys.dont_write_bytecode = True

_TARGET = os.environ.get("LAB_TARGET", "starter")
_LAB_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_LAB_DIR / _TARGET))
TARGET_DIR = _LAB_DIR / _TARGET


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch):
    """Never let a test see the real home directory or a real EXPENSE_FILE."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("EXPENSE_FILE", raising=False)


@pytest.fixture
def data_file(tmp_path):
    return tmp_path / "data" / "expenses.json"
