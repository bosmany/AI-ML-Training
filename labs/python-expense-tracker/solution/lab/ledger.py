"""Pure domain logic: no argparse, no printing, no file access."""
from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass

from .errors import NotFoundError, ValidationError
from .store import Expense, Store
from .validate import normalize_category


@dataclass(frozen=True)
class BudgetWarning:
    category: str
    month: tuple[int, int]
    spent_cents: int
    limit_cents: int


def add_expense(store: Store, *, amount_cents: int, category: str, day: dt.date, note: str = "") -> Expense:
    """Validate, then append to ``store`` and return the new expense.

    On any ValidationError the store is left unchanged.
    """
    cat = normalize_category(category)
    if amount_cents <= 0:
        raise ValidationError("amount must be greater than zero")
    if store.budgets and cat not in store.budgets:
        known = ", ".join(sorted(store.budgets))
        raise ValidationError(f"unknown category {cat!r}: budgets are set for {known}")
    expense = Expense(store.next_id, amount_cents, cat, day, note.strip())
    store.expenses.append(expense)
    store.next_id += 1
    return expense


def remove_expense(store: Store, expense_id: int) -> Expense:
    for i, e in enumerate(store.expenses):
        if e.id == expense_id:
            return store.expenses.pop(i)
    raise NotFoundError(f"no expense with id {expense_id}")


def set_budget(store: Store, category: str, limit_cents: int) -> None:
    cat = normalize_category(category)
    if limit_cents <= 0:
        raise ValidationError("budget must be greater than zero")
    store.budgets[cat] = limit_cents


def filter_expenses(expenses: Iterable[Expense], *, category: str | None = None, since: dt.date | None = None,
                    until: dt.date | None = None) -> list[Expense]:
    """Filter (``since``/``until`` inclusive) and sort by ``(date, id)``."""
    cat = normalize_category(category) if category is not None else None
    out = [e for e in expenses
           if (cat is None or e.category == cat)
           and (since is None or e.date >= since)
           and (until is None or e.date <= until)]
    return sorted(out, key=lambda e: (e.date, e.id))


def month_totals(expenses: Iterable[Expense], month: tuple[int, int]) -> dict[str, int]:
    """Cents per category for ``(year, month)``, keys sorted alphabetically."""
    totals: dict[str, int] = {}
    for e in expenses:
        if (e.date.year, e.date.month) == month:
            totals[e.category] = totals.get(e.category, 0) + e.amount_cents
    return dict(sorted(totals.items()))


def budget_warnings(store: Store, month: tuple[int, int]) -> list[BudgetWarning]:
    """One warning per category whose spending STRICTLY exceeds its budget, sorted by category."""
    totals = month_totals(store.expenses, month)
    return [BudgetWarning(cat, month, totals[cat], limit)
            for cat, limit in sorted(store.budgets.items())
            if totals.get(cat, 0) > limit]
