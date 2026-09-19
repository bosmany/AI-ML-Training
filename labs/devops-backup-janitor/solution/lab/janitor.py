"""Scan a directory of dated backups, apply retention, delete safely, write a manifest."""
from __future__ import annotations

import os
import random
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .fsops import FileLock, UnsafePathError, safe_delete, write_manifest_atomic
from .policy import Backup, Policy, series_of
from .retention import Decision, decide
from .retry import retry_with_backoff

MANIFEST_NAME = ".janitor-manifest.json"
LOCK_NAME = ".janitor.lock"


@dataclass
class RunResult:
    dry_run: bool
    decisions: list[Decision] = field(default_factory=list)
    unmanaged: list[tuple[str, str]] = field(default_factory=list)  # (name, why it was left alone)
    deleted: list[str] = field(default_factory=list)  # actually removed (always empty for a dry run)
    errors: list[tuple[str, str]] = field(default_factory=list)
    unsafe: list[str] = field(default_factory=list)

    @property
    def to_delete(self) -> list[Decision]:
        return [d for d in self.decisions if not d.keep]

    @property
    def kept(self) -> list[Decision]:
        return [d for d in self.decisions if d.keep]


def scan_backups(target: Path) -> tuple[list[Backup], list[tuple[str, str]]]:
    """Backups directly inside ``target`` (files or directories named ``<series>-<year>...``).

    Dot-files (lock, manifest), symlinks and names without a series are reported as unmanaged and are
    never candidates for deletion. mtimes are read WITHOUT following symlinks.
    """
    backups: list[Backup] = []
    unmanaged: list[tuple[str, str]] = []
    with os.scandir(target) as it:
        for entry in sorted(it, key=lambda e: e.name):
            if entry.name.startswith("."):
                continue
            if entry.is_symlink():
                unmanaged.append((entry.name, "symlink"))
                continue
            series = series_of(entry.name)
            if series is None:
                unmanaged.append((entry.name, "no series in name"))
                continue
            mtime = datetime.fromtimestamp(entry.stat(follow_symlinks=False).st_mtime, tz=timezone.utc)
            backups.append(Backup(Path(entry.path), entry.name, series, mtime))
    return backups, unmanaged


def run(
    target: Path,
    policies: Mapping[str, Policy],
    default: Policy | None = None,
    *,
    now: datetime,
    dry_run: bool = True,
    remove: Callable[[Path, Path], None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    rng: Callable[[], float] = random.random,
) -> RunResult:
    """Apply retention to ``target``. DRY RUN BY DEFAULT: pass ``dry_run=False`` to delete.

    Series without a policy (and no ``default``) are left untouched. Deletions are retried with backoff on
    OSError; an unsafe path is never retried. A manifest of what was kept/deleted is written atomically after a
    real run. Raises ``NotADirectoryError`` for a bad target and ``LockHeldError`` if another run is active.
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    remove = remove or safe_delete  # looked up at call time so tests can substitute it
    target = Path(target)
    if not target.is_dir():
        raise NotADirectoryError(f"{target} is not a directory")
    target = target.resolve()

    with FileLock(target / LOCK_NAME):
        backups, unmanaged = scan_backups(target)
        result = RunResult(dry_run=dry_run, unmanaged=unmanaged)
        by_series: dict[str, list[Backup]] = {}
        for b in backups:
            by_series.setdefault(b.series, []).append(b)
        for series in sorted(by_series):
            policy = policies.get(series, default)
            if policy is None:
                result.decisions += [Decision(b, True, ("no-policy",)) for b in by_series[series]]
                continue
            result.decisions += decide(by_series[series], policy, now)

        if dry_run:
            return result

        for d in result.to_delete:
            try:
                retry_with_backoff(lambda: remove(target, d.backup.path), retry_on=(OSError,), sleep=sleep, rng=rng)
                result.deleted.append(d.backup.name)
            except UnsafePathError as exc:
                result.unsafe.append(d.backup.name)
                result.errors.append((d.backup.name, str(exc)))
            except OSError as exc:
                result.errors.append((d.backup.name, f"{type(exc).__name__}: {exc}"))

        failed = {name for name, _ in result.errors}
        write_manifest_atomic(target / MANIFEST_NAME, {
            "generated_at": now.isoformat(),
            "target": str(target),
            "kept": [{"name": d.backup.name, "series": d.backup.series, "reasons": list(d.reasons)}
                     for d in result.decisions if d.keep or d.backup.name in failed],
            "deleted": sorted(result.deleted),
            "errors": [{"name": n, "error": e} for n, e in result.errors],
        })
    return result
