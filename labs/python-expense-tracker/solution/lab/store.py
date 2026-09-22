"""The JSON data file: load, validate, and save atomically."""
from __future__ import annotations

import contextlib
import datetime as dt
import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import CorruptDataError, ValidationError
from .validate import normalize_category, parse_date

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
    next_id: int = 1


def resolve_path(file_arg: str | None, environ: Mapping[str, str]) -> Path:
    """``--file`` wins, then ``EXPENSE_FILE`` (empty counts as unset), then ``~/.expenses.json``."""
    if file_arg:
        return Path(file_arg).expanduser()
    env = environ.get("EXPENSE_FILE")
    if env:
        return Path(env).expanduser()
    return Path.home() / DEFAULT_FILENAME


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def load_store(path: Path) -> Store:
    """Read the store. A missing file is an empty store (and is NOT created).

    Anything unreadable or structurally wrong raises ``CorruptDataError``; the file is never modified.
    """
    def corrupt(why: str) -> CorruptDataError:
        return CorruptDataError(f"{path}: corrupt data file ({why})")

    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Store()
    except (OSError, UnicodeDecodeError) as exc:
        raise corrupt(f"cannot read: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise corrupt(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise corrupt("top level must be an object")
    expenses_raw, budgets_raw, next_id = data.get("expenses"), data.get("budgets"), data.get("next_id")
    if not isinstance(expenses_raw, list) or not isinstance(budgets_raw, dict) or not _is_int(next_id):
        raise corrupt("missing or malformed 'expenses', 'budgets' or 'next_id'")

    budgets: dict[str, int] = {}
    for cat, limit in budgets_raw.items():
        if not isinstance(cat, str) or not _is_int(limit) or limit <= 0:
            raise corrupt(f"bad budget entry {cat!r}")
        budgets[cat] = limit

    expenses: list[Expense] = []
    seen: set[int] = set()
    for item in expenses_raw:
        if not isinstance(item, dict):
            raise corrupt("expense entry is not an object")
        eid, cents, cat, day, note = (item.get(k) for k in ("id", "amount_cents", "category", "date", "note"))
        if not _is_int(eid) or eid in seen or eid >= next_id:
            raise corrupt(f"bad or duplicate id {eid!r}")
        if not _is_int(cents) or cents <= 0:
            raise corrupt(f"expense {eid}: amount_cents must be a positive integer")
        if not isinstance(cat, str) or not isinstance(note, str) or not isinstance(day, str):
            raise corrupt(f"expense {eid}: category, date and note must be strings")
        try:
            normalize_category(cat)
            parsed = parse_date(day)
        except ValidationError as exc:
            raise corrupt(f"expense {eid}: {exc}") from exc
        seen.add(eid)
        expenses.append(Expense(eid, cents, cat, parsed, note))
    return Store(expenses=expenses, budgets=budgets, next_id=next_id)


def save_store(path: Path, store: Store) -> None:
    """Write atomically: temp file in the SAME directory, flush + fsync, then ``os.replace``.

    On any failure the original file is untouched and no temp file is left behind.
    """
    data = {
        "version": 1,
        "next_id": store.next_id,
        "budgets": dict(sorted(store.budgets.items())),
        "expenses": [e.to_dict() for e in store.expenses],
    }
    text = json.dumps(data, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise
