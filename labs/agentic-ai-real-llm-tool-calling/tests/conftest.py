"""Pick which implementation the tests import as ``lab``.

Learners run ``pytest`` (target = starter). Maintainers/CI run
``LAB_TARGET=solution pytest``. See labs/README.md and this lab's README.md.
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True

_TARGET = os.environ.get("LAB_TARGET", "starter")
_LAB_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_LAB_DIR / _TARGET))
