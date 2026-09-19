"""Command line: ``janitor DIR --keep-last 3 --series db=daily:7,monthly:6 --execute``."""
from __future__ import annotations

import argparse
import random
import time
from collections.abc import Callable

from .janitor import RunResult

EXIT_OK = 0
EXIT_DELETE_FAILED = 1  # some deletions failed (the rest were done)
EXIT_USAGE = 2  # bad arguments / policy / target
EXIT_LOCKED = 3  # another run holds the lock
EXIT_UNSAFE = 4  # a path resolved outside the target and was refused


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="janitor", description="Retention for a directory of dated backups.")
    p.add_argument("target")
    p.add_argument("--keep-last", type=int, default=0)
    p.add_argument("--keep-daily", type=int, default=0)
    p.add_argument("--keep-weekly", type=int, default=0)
    p.add_argument("--keep-monthly", type=int, default=0)
    p.add_argument("--series", action="append", default=[], metavar="NAME=last:3,daily:7",
                   help="per-series policy (repeatable); overrides the default policy for that series")
    p.add_argument("--protect-hours", type=float, default=0.0, help="never delete backups younger than this")
    p.add_argument("--execute", action="store_true", help="really delete (default is a dry run)")
    p.add_argument("--now", help="ISO-8601 timestamp with timezone to use as 'now' (for reproducible runs)")
    return p


def _summary(result: RunResult) -> str:
    verb = "would delete" if result.dry_run else "deleted"
    names = [d.backup.name for d in result.to_delete] if result.dry_run else result.deleted
    lines = [f"{'DRY RUN' if result.dry_run else 'EXECUTED'}: kept {len(result.kept)}, {verb} {len(names)}"]
    lines += [f"  - {n}" for n in names]
    lines += [f"  ! {n}: {e}" for n, e in result.errors]
    return "\n".join(lines)


def main(
    argv: list[str] | None = None,
    *,
    sleep: Callable[[float], None] = time.sleep,
    rng: Callable[[], float] = random.random,
) -> int:
    """Run the tool and RETURN an exit code (never sys.exit).

    TODO:
    - argparse exits on bad input: catch SystemExit and return its code (EXIT_USAGE for errors).
    - default policy from --keep-* (None when all are 0), per-series policies from repeated
      ``--series NAME=last:3,daily:7`` (use parse_policy; missing "=" -> error). --protect-hours applies to all.
    - refuse (EXIT_USAGE) when neither a default nor any series policy was given, on a bad --now, a missing
      target or any ValueError. Messages go to stderr.
    - ``now`` = ``datetime.fromisoformat(--now)`` or the current UTC time.
    - call ``run(..., dry_run=not args.execute, sleep=sleep, rng=rng)``; LockHeldError -> EXIT_LOCKED.
    - print ``_summary(result)``; return EXIT_UNSAFE if result.unsafe, else EXIT_DELETE_FAILED if result.errors,
      else EXIT_OK.
    """
    raise NotImplementedError
