"""Command line: ``janitor DIR --keep-last 3 --series db=daily:7,monthly:6 --execute``."""
from __future__ import annotations

import argparse
import random
import sys
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from .fsops import LockHeldError
from .janitor import RunResult, run
from .policy import Policy, parse_policy

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
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else EXIT_USAGE
    try:
        protect = timedelta(hours=args.protect_hours)
        counts = dict(keep_last=args.keep_last, keep_daily=args.keep_daily,
                      keep_weekly=args.keep_weekly, keep_monthly=args.keep_monthly)
        default: Policy | None = Policy(**counts, protect_younger_than=protect) if any(counts.values()) else None
        policies: dict[str, Policy] = {}
        for item in args.series:
            name, sep, spec = item.partition("=")
            if not sep or not name:
                raise ValueError(f"bad --series {item!r}; expected NAME=last:3,daily:7")
            policies[name] = parse_policy(spec, protect)
        now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
        if not policies and default is None:
            raise ValueError("give at least one --keep-* option or --series (refusing to guess a policy)")
        result = run(args.target, policies, default, now=now, dry_run=not args.execute, sleep=sleep, rng=rng)
    except LockHeldError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_LOCKED
    except (ValueError, NotADirectoryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    print(_summary(result))
    if result.unsafe:
        return EXIT_UNSAFE
    return EXIT_DELETE_FAILED if result.errors else EXIT_OK
