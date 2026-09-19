"""Scan a directory of dated backups, apply retention, delete safely, write a manifest."""
from __future__ import annotations

import random
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .fsops import safe_delete  # noqa: F401
from .policy import Backup, Policy
from .retention import Decision

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
    """Return (backups, unmanaged) for the entries directly inside ``target``.

    TODO: use ``os.scandir`` (sorted by name).
    - names starting with "." (lock file, manifest) are skipped silently
    - symlinks -> unmanaged with reason "symlink" (never follow them)
    - names ``series_of`` cannot parse -> unmanaged with reason "no series in name"
    - everything else (files AND directories) is a Backup; mtime = ``entry.stat(follow_symlinks=False).st_mtime``
      converted to an aware UTC datetime.
    """
    raise NotImplementedError


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
    """Apply retention to ``target``. DRY RUN BY DEFAULT.

    TODO, in this order:
    1. naive ``now`` -> ValueError; ``target`` not a directory -> NotADirectoryError; resolve it.
    2. ``remove`` defaults to ``safe_delete`` - look it up when called (``remove = remove or safe_delete``) so
       tests can substitute ``lab.janitor.safe_delete``.
    3. take ``FileLock(target / LOCK_NAME)`` for the whole run (LockHeldError propagates).
    4. scan, group by series; policy = policies.get(series, default). No policy -> keep everything with reason
       "no-policy". Otherwise ``decide``. Fill ``RunResult.decisions`` / ``unmanaged``.
    5. dry run: return now - no deletions, no manifest.
    6. delete each doomed backup via ``retry_with_backoff(lambda: remove(target, path), retry_on=(OSError,),
       sleep=sleep, rng=rng)``. ``UnsafePathError`` (not an OSError, never retried) -> ``result.unsafe`` and
       ``result.errors``; other OSError -> ``result.errors`` as (name, "Type: message"). Keep going after failures.
    7. write the manifest atomically to ``target / MANIFEST_NAME``: {generated_at (iso), target, kept: [{name,
       series, reasons}] (also files that FAILED to delete - they are still there), deleted: [sorted names],
       errors: [{name, error}]}.
    """
    raise NotImplementedError
