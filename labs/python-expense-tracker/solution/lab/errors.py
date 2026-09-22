"""Exit codes and the exception hierarchy. Provided - you do not need to change this file."""
from __future__ import annotations

EXIT_OK = 0
EXIT_USAGE = 2       # argparse's own code for usage errors; also used for rejected input
EXIT_NOT_FOUND = 3
EXIT_CORRUPT = 4


class ExpenseError(Exception):
    """Base class: ``main`` prints ``str(exc)`` to stderr and returns ``exc.exit_code``."""

    exit_code: int = 1


class ValidationError(ExpenseError):
    """User input was rejected (bad amount, date, category...). Nothing may have been written."""

    exit_code = EXIT_USAGE


class NotFoundError(ExpenseError):
    """The requested expense does not exist."""

    exit_code = EXIT_NOT_FOUND


class CorruptDataError(ExpenseError):
    """The data file exists but is not a valid expense store. The file must be left untouched."""

    exit_code = EXIT_CORRUPT
