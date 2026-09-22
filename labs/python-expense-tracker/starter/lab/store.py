"""The JSON data file: load, validate, and save atomically."""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import CorruptDataError, ValidationError  # noqa: F401  (you will raise them)

DEFAULT_FILENAME = ".expenses.json"


@dataclass(frozen=True)
class Expense:
    id: int
    amount_cents: int
    category: str
    date: dt.date
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "amount_cents": self.amount_cents, "category": self.category,
                "date": self.date.isoformat(), "note": self.note}


@dataclass
class Store:
    expenses: list[Expense] = field(default_factory=list)
    budgets: dict[str, int] = field(default_factory=dict)  # category -> monthly limit in cents
    next_id: int = 1  # ids come from this counter so a removed id is never handed out again


def resolve_path(file_arg: str | None, environ: Mapping[str, str]) -> Path:
    """Where is the data file?

    TODO: ``--file`` value wins, then ``EXPENSE_FILE`` (an empty string counts as unset), then
    ``Path.home() / DEFAULT_FILENAME``. Expand ``~`` in the first two.
    """
    raise NotImplementedError


def load_store(path: Path) -> Store:
    """Read and validate the store.

    TODO:
    - a missing file is an empty ``Store()`` and must NOT be created
    - JSON layout: ``{"version": 1, "next_id": int, "budgets": {cat: cents}, "expenses": [ {id, amount_cents,
      category, date, note}, ... ]}``
    - unreadable file, invalid/truncated/empty JSON, wrong top-level type, missing keys, wrong types (a ``bool`` or
      ``float`` is not an int!), non-positive amounts/budgets, bad dates, duplicate ids, or ``next_id`` not greater
      than every id -> ``CorruptDataError`` whose message names the path
    - never modify the file
    """
    raise NotImplementedError


def save_store(path: Path, store: Store) -> None:
    """Write the store so that a crash can never leave a half-written file.

    TODO:
    - create missing parent directories
    - write ``json.dumps(..., indent=2)`` in the layout above to a temp file IN THE SAME DIRECTORY
      (``tempfile.mkstemp(dir=path.parent)``), ``flush()`` + ``os.fsync()``, then ``os.replace(tmp, path)``
    - if anything fails, remove the temp file and re-raise; the original file stays as it was
    """
    raise NotImplementedError
