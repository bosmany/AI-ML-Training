"""Thin argparse layer over the domain modules. ``main`` returns the exit code.

The parser is provided. You write the command handlers and ``main``.
"""
from __future__ import annotations

import argparse
import datetime as dt
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from .errors import EXIT_OK, ExpenseError  # noqa: F401

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


def cmd_add(args: argparse.Namespace, path: Path, today: Today) -> int:
    """``add``: parse -> load -> ``add_expense`` -> save -> print ONLY the new id on stdout.

    TODO:
    - validate amount/date BEFORE touching the file; ``--date`` defaults to ``today()``
    - after saving, if the expense's category is now over budget for that month, print a warning to STDERR
      (still exit 0). Wording: ``warning: over budget for food in 2025-03: spent 320.50 of 300.00``
    """
    raise NotImplementedError


def cmd_list(args: argparse.Namespace, path: Path, today: Today) -> int:
    """``list``: apply the filters; print a table or, with ``--json``, a JSON array.

    TODO:
    - table: first line is the header ``ID DATE CATEGORY AMOUNT NOTE`` (columns padded with spaces), then one line
      per expense sorted by (date, id); amounts like ``12.50``. An empty store prints only the header and exits 0.
    - ``--json``: ``[{"id", "date", "category", "amount": "12.50", "amount_cents": 1250, "note"}, ...]``
      (``[]`` when empty)
    """
    raise NotImplementedError


def cmd_report(args: argparse.Namespace, path: Path, today: Today) -> int:
    """``report --month YYYY-MM``.

    TODO:
    - text: one ``<category> <amount>`` line per category (alphabetical) then ``TOTAL <amount>``; an empty month is
      just ``TOTAL 0.00``. The total is the sum of the row cents.
    - ``--json``: ``{"month", "categories": {cat: "0.30"}, "total": "5.30", "total_cents": 530}``
    - budget warnings for every exceeded category go to STDERR (stdout stays clean)
    """
    raise NotImplementedError


def cmd_remove(args: argparse.Namespace, path: Path, today: Today) -> int:
    """``remove ID``: remove, save, print ``removed <id>``. Unknown id -> NotFoundError (exit 3), file untouched."""
    raise NotImplementedError


def cmd_budget(args: argparse.Namespace, path: Path, today: Today) -> int:
    """``budget set CATEGORY AMOUNT`` (amount in currency units, ``300`` = 300.00) prints ``budget food 300.00``;
    ``budget list`` prints ``<category> <amount>`` lines sorted by category."""
    raise NotImplementedError


def main(argv: Sequence[str] | None = None, *, today: Today = dt.date.today,
         environ: Mapping[str, str] | None = None) -> int:
    """Run the CLI and RETURN the exit code (tests call ``main([...])`` directly).

    TODO:
    - ``build_parser().parse_args(argv)``; argparse calls ``sys.exit`` on usage errors and ``--help``:
      catch ``SystemExit`` and return its code (2 for usage errors, 0 for help)
    - resolve the data file with ``resolve_path(getattr(args, "file", None), environ or os.environ)`` - look at
      ``os.environ`` when called, not at import time
    - dispatch to the ``cmd_*`` handler for ``args.command``
    - catch ``ExpenseError``: print ``expense: error: <message>`` to STDERR, return ``exc.exit_code``
      (2 invalid input, 3 not found, 4 corrupt file). Results go to stdout, errors to stderr.
    """
    raise NotImplementedError
