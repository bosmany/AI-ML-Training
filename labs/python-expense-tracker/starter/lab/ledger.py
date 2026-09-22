"""Pure domain logic: no argparse, no printing, no file access."""
from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass

from .errors import NotFoundError, ValidationError  # noqa: F401  (you will raise them)
from .store import Expense, Store


@dataclass(frozen=True)
class BudgetWarning:
    category: str
    month: tuple[int, int]
    spent_cents: int
    limit_cents: int


def add_expense(store: Store, *, amount_cents: int, category: str, day: dt.date, note: str = "") -> Expense:
    """Validate, append to ``store`` and return the new expense.

    TODO:
    - normalize the category (``normalize_category``); ``amount_cents`` must be > 0
    - if the store has ANY budget, the category must be one of the budgeted ones, else ``ValidationError``
      (message names the category)
    - id = ``store.next_id``; then increment it; strip the note
    - on a ValidationError the store must be left completely unchanged
    """
    raise NotImplementedError


def remove_expense(store: Store, expense_id: int) -> Expense:
    """Remove and return the expense; unknown id -> ``NotFoundError``."""
    raise NotImplementedError


def set_budget(store: Store, category: str, limit_cents: int) -> None:
    """Set/overwrite the monthly budget of a (normalized) category; limit must be > 0 else ``ValidationError``."""
    raise NotImplementedError


def filter_expenses(expenses: Iterable[Expense], *, category: str | None = None, since: dt.date | None = None,
                    until: dt.date | None = None) -> list[Expense]:
    """Filter and return a NEW list sorted by ``(date, id)``.

    TODO: ``category`` is normalized before comparing; ``since`` and ``until`` are inclusive; ``None`` = no limit.
    """
    raise NotImplementedError


def month_totals(expenses: Iterable[Expense], month: tuple[int, int]) -> dict[str, int]:
    """Cents per category for ``(year, month)`` - other months (and other years!) excluded.

    TODO: integer arithmetic only; return the dict with keys sorted alphabetically.
    """
    raise NotImplementedError


def budget_warnings(store: Store, month: tuple[int, int]) -> list[BudgetWarning]:
    """One ``BudgetWarning`` per category whose spending in ``month`` is STRICTLY greater than its budget.

    TODO: exactly at the limit is fine; categories without a budget never warn; sort by category.
    """
    raise NotImplementedError
