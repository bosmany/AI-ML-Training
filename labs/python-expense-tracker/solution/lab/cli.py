"""Thin argparse layer over the domain modules. ``main`` returns the exit code."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from .errors import EXIT_OK, ExpenseError
from .ledger import (BudgetWarning, add_expense, budget_warnings, filter_expenses, month_totals, remove_expense,
                     set_budget)
from .store import load_store, resolve_path, save_store
from .validate import format_cents, normalize_category, parse_amount, parse_date, parse_month

Today = Callable[[], dt.date]


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--file", default=argparse.SUPPRESS, help="data file (default: $EXPENSE_FILE or ~/.expenses.json)")
    parser = argparse.ArgumentParser(prog="expense", description="Track spending in a JSON file.", parents=[common])
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("add", parents=[common], help="record an expense and print its id")
    p.add_argument("--amount", required=True, help="e.g. 12.50")
    p.add_argument("--category", required=True)
    p.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p.add_argument("--note", default="")

    p = sub.add_parser("list", parents=[common], help="list expenses")
    p.add_argument("--category")
    p.add_argument("--since", help="YYYY-MM-DD, inclusive")
    p.add_argument("--until", help="YYYY-MM-DD, inclusive")
    p.add_argument("--json", action="store_true", help="machine-readable output")

    p = sub.add_parser("report", parents=[common], help="totals per category for a month")
    p.add_argument("--month", required=True, help="YYYY-MM")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("remove", parents=[common], help="delete an expense by id")
    p.add_argument("id", type=int)

    p = sub.add_parser("budget", parents=[common], help="monthly per-category budgets")
    bsub = p.add_subparsers(dest="budget_command", required=True)
    b = bsub.add_parser("set", parents=[common], help="expense budget set food 300")
    b.add_argument("category")
    b.add_argument("amount")
    bsub.add_parser("list", parents=[common], help="show budgets")
    return parser


def _warning_text(w: BudgetWarning) -> str:
    return (f"warning: over budget for {w.category} in {w.month[0]:04d}-{w.month[1]:02d}: "
            f"spent {format_cents(w.spent_cents)} of {format_cents(w.limit_cents)}")


def cmd_add(args: argparse.Namespace, path: Path, today: Today) -> int:
    amount = parse_amount(args.amount)
    day = parse_date(args.date) if args.date else today()
    store = load_store(path)
    expense = add_expense(store, amount_cents=amount, category=args.category, day=day, note=args.note or "")
    save_store(path, store)
    print(expense.id)
    for w in budget_warnings(store, (day.year, day.month)):
        if w.category == expense.category:
            print(_warning_text(w), file=sys.stderr)
    return EXIT_OK


def cmd_list(args: argparse.Namespace, path: Path, today: Today) -> int:
    since = parse_date(args.since) if args.since else None
    until = parse_date(args.until) if args.until else None
    rows = filter_expenses(load_store(path).expenses, category=args.category, since=since, until=until)
    if args.json:
        print(json.dumps([{"id": e.id, "date": e.date.isoformat(), "category": e.category,
                           "amount": format_cents(e.amount_cents), "amount_cents": e.amount_cents,
                           "note": e.note} for e in rows], indent=2))
        return EXIT_OK
    table = [("ID", "DATE", "CATEGORY", "AMOUNT", "NOTE")]
    table += [(str(e.id), e.date.isoformat(), e.category, format_cents(e.amount_cents), e.note) for e in rows]
    widths = [max(len(r[i]) for r in table) for i in range(4)]
    for r in table:
        print(("  ".join(r[i].ljust(widths[i]) for i in range(4)) + "  " + r[4]).rstrip())
    return EXIT_OK


def cmd_report(args: argparse.Namespace, path: Path, today: Today) -> int:
    month = parse_month(args.month)
    store = load_store(path)
    totals = month_totals(store.expenses, month)
    total = sum(totals.values())
    if args.json:
        print(json.dumps({"month": args.month, "categories": {c: format_cents(v) for c, v in totals.items()},
                          "total": format_cents(total), "total_cents": total}, indent=2))
    else:
        rows = [(c, format_cents(v)) for c, v in totals.items()] + [("TOTAL", format_cents(total))]
        width = max(len(r[0]) for r in rows)
        for name, amount in rows:
            print(f"{name.ljust(width)}  {amount}")
    for w in budget_warnings(store, month):
        print(_warning_text(w), file=sys.stderr)
    return EXIT_OK


def cmd_remove(args: argparse.Namespace, path: Path, today: Today) -> int:
    store = load_store(path)
    removed = remove_expense(store, args.id)
    save_store(path, store)
    print(f"removed {removed.id}")
    return EXIT_OK


def cmd_budget(args: argparse.Namespace, path: Path, today: Today) -> int:
    store = load_store(path)
    if args.budget_command == "set":
        limit = parse_amount(args.amount)
        set_budget(store, args.category, limit)
        save_store(path, store)
        print(f"budget {normalize_category(args.category)} {format_cents(limit)}")
    else:
        for cat, limit in sorted(store.budgets.items()):
            print(f"{cat} {format_cents(limit)}")
    return EXIT_OK


_HANDLERS: dict[str, Callable[[argparse.Namespace, Path, Today], int]] = {
    "add": cmd_add, "list": cmd_list, "report": cmd_report, "remove": cmd_remove, "budget": cmd_budget,
}


def main(argv: Sequence[str] | None = None, *, today: Today = dt.date.today,
         environ: Mapping[str, str] | None = None) -> int:
    """Run the CLI and return the exit code (never raises SystemExit)."""
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    path = resolve_path(getattr(args, "file", None), os.environ if environ is None else environ)
    try:
        return _HANDLERS[args.command](args, path, today)
    except ExpenseError as exc:
        print(f"expense: error: {exc}", file=sys.stderr)
        return exc.exit_code
