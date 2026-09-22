# Lab: Expense Tracker CLI (money as integer cents, atomic JSON store, exit codes, budgets)

Build a small command-line tool that records spending in a JSON file: `expense add`, `list`, `report`, `remove`
and per-category monthly budgets. This is the **guided** tier of the project *Expense Tracker CLI*: the parser,
exception classes, dataclasses and docstrings with TODOs are given; you write the logic that makes it correct.

## Why it matters in a real job

Almost every internal tool is "a CLI over a file": deploy helpers, inventory scripts, report generators. What
separates a script from a tool is exactly what this lab drills: money never touches a `float`, bad input is rejected
with **no partial write**, a crash mid-write cannot corrupt the data file, results go to stdout and errors to
stderr, and the exit code tells a calling script what happened (0 ok, 2 bad input, 3 not found, 4 corrupt file).

## Prerequisites (course chapters)

- [Functions and modules](../../python/ch03-functions-modules.html)
- [Files, errors and more](../../python/ch05-oop-files-errors.html)
- [Professional Python](../../python/ch06-professional-python.html)
- [OOP deep dive 4: designing with objects](../../python/oop04-composition-dataclasses-design.html)

## Run it

```bash
cd labs/python-expense-tracker
python -m venv .venv && source .venv/bin/activate    # optional but recommended
pip install -r requirements.txt
pytest -q                        # starter: every test fails until you implement it
LAB_TARGET=solution pytest -q    # maintainers / CI: the reference solution passes
```

Tests use `tmp_path`, point `HOME` at a temporary directory and never read your real `EXPENSE_FILE`. Nothing is
written outside the temp directory and nothing sleeps. Once it works you can try it for real:

```bash
cd starter && python -m lab --file /tmp/demo.json add --amount 12.50 --category food --date 2025-03-01
```

## What is provided vs what you write

Provided: `errors.py` (exit codes and exceptions), the `Expense`/`Store`/`BudgetWarning` dataclasses, `build_parser()`
in `cli.py` and `python -m lab`. You write `validate.py`, `store.py` (`resolve_path`, `load_store`, `save_store`),
`ledger.py` and the command handlers plus `main` in `cli.py`.

## Behaviour to implement

- Amounts are strings like `12.50` -> **integer cents**. At most 2 decimals (a third is rejected, never rounded), strictly positive.
- Dates are strict `YYYY-MM-DD` and must exist (`2025-02-30` and `2025-13-01` are rejected); months are `YYYY-MM`.
- The data file path comes from `--file`, else `EXPENSE_FILE`, else `~/.expenses.json`. A missing file is an empty store.
- `add` prints only the new id; ids come from a counter in the file and are never reused.
- `list` prints a header `ID DATE CATEGORY AMOUNT NOTE` and rows sorted by (date, id); `--category`, `--since`, `--until`
  (inclusive) filter; `--json` prints an array. An empty store is a header only (or `[]`), exit 0.
- `report --month 2025-03` prints `<category> <amount>` lines and a final `TOTAL <amount>`; `--json` variant.
- `budget set food 300` / `budget list`. Once any budget exists, adding to an unbudgeted category is rejected. When a
  month's spending in a category is **strictly above** its budget, `add` and `report` print a `warning: over budget ...` line to
  **stderr** and still exit 0.
- Exit codes: `0` ok, `2` invalid input or usage, `3` unknown id, `4` corrupt data file (which is left untouched). Errors go to stderr.

## Tasks

1. `validate.py`: `parse_amount`, `format_cents`, `parse_date`, `parse_month`, `normalize_category`.
2. `ledger.py`: `add_expense`, `remove_expense`, `set_budget`, `filter_expenses`, `month_totals`, `budget_warnings` (pure functions).
3. `store.py`: `resolve_path`, `load_store` (detect every kind of corruption), `save_store` (atomic).
4. `cli.py`: the five `cmd_*` handlers and `main(argv)` returning the exit code.

Suggested order: follow the numbers; `pytest -q -x` shows the first thing still missing.

## Hints

<details><summary>Exact money</summary>

Never `float(text)`. Validate the shape with a regex (`[0-9]+(\.[0-9]{1,2})?`), then `int(Decimal(text) * 100)` is exact
because there are at most two decimals. Print with `divmod(cents, 100)`.
</details>

<details><summary>date.fromisoformat is too forgiving</summary>

On Python 3.11+ `date.fromisoformat("20250301")` succeeds. Check the shape with a regex first, then let `date(y, m, d)`
reject `2025-02-30` (it raises `ValueError`; convert it to `ValidationError`).
</details>

<details><summary>Atomic writes</summary>

`os.replace` is atomic only on one filesystem, so create the temp file next to the target
(`tempfile.mkstemp(dir=path.parent)`), write, `flush()`, `os.fsync()`, then `os.replace(tmp, path)`. Wrap it in
`try/except BaseException` to delete the temp file when anything fails and re-raise.
</details>

<details><summary>Corrupt vs missing</summary>

`FileNotFoundError` is normal (empty store). Everything else that goes wrong while reading or validating is
`CorruptDataError`. Remember `isinstance(True, int)` is `True` - reject bools where an int is expected.
</details>

<details><summary>main() and SystemExit</summary>

`parser.parse_args` calls `sys.exit(2)` on a usage error. Catch `SystemExit` in `main` and return its code so tests
(and callers) get an int. Handle `ExpenseError` once, at the bottom of `main`, using `exc.exit_code`.
</details>

## Stretch goals

- Make it installable: add a `pyproject.toml` with a `[project.scripts] expense = "lab.cli:main"` entry (adapt `main` to `sys.exit(main())`), then `pipx install .`.
- `expense import bank.csv --map date=Date,amount=Amount` reporting imported / duplicate / rejected rows.
- A plugin API with `importlib.metadata.entry_points(group="expense.plugins")`.
- Cross-process safety: a lock file so two `expense add` runs cannot both read id 7.
- Currency support: a `--currency` option and per-currency totals.

## How this comes up in interviews

"Write a small CLI that tracks X" is a common take-home. Reviewers look for: money as integers or `Decimal`, domain
logic separated from `argparse`/printing (so it is testable), atomic file writes, meaningful exit codes, errors on
stderr, and tests that never touch the real home directory. Be ready to answer *why not floats?*, *what if the
process dies while writing?* and *how would two concurrent runs behave?*

## What this lab does not cover

- Packaging and publishing (`pyproject.toml`, TestPyPI, `pipx`) - the tests import the `lab` package directly.
- Concurrent writers: the load-modify-save cycle has no lock, so two simultaneous runs can lose an update.
- Multiple currencies, rounding rules for division/tax, or localisation of number formats.
- Ruff, mypy and coverage gates from the project's quality rubric are not enforced by these tests.
