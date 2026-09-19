"""Filesystem safety: guarded deletes, atomic manifest writes and a lock file."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


class UnsafePathError(ValueError):
    """A path resolves outside the target directory (``..`` traversal or a symlink)."""


class LockHeldError(RuntimeError):
    """Another run holds the lock."""


def safe_delete(target: Path, path: Path) -> None:
    """Delete ``path`` (file or directory tree) ONLY if it lives strictly inside ``target``.

    TODO:
    - refuse symlinks outright (raise UnsafePathError) - never follow or delete them
    - ``resolve()`` both paths: refuse when the result is the target itself or not inside it
      (``Path.is_relative_to``). This stops ``target/../x`` and ``target/linkdir/file``
    - a resolved directory -> ``shutil.rmtree``; a file -> ``unlink``
    - ``target`` may itself be reached through a symlink: resolve it before comparing.
    """
    raise NotImplementedError


def write_manifest_atomic(path: Path, data: dict[str, Any]) -> None:
    """Write ``data`` as JSON so that neither a reader nor a crash ever sees a half-written file.

    TODO: write to a temp file in the SAME directory (``os.replace`` is only atomic within one filesystem),
    flush + ``os.fsync``, then ``os.replace(tmp, path)``. If anything fails, remove the temp file and re-raise;
    the previous manifest must stay intact.
    """
    raise NotImplementedError


class FileLock:
    """Exclusive lock file usable as a context manager."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._held = False

    def __enter__(self) -> FileLock:
        """TODO: create the file with ``os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)`` - atomic, no
        check-then-create race. Write our pid into it. If it already exists raise LockHeldError whose message
        contains the owner's pid (read it from the file) and how to clear a stale lock."""
        raise NotImplementedError

    def __exit__(self, *exc: object) -> None:
        """TODO: remove the lock file - but ONLY if this object acquired it (a loser must not delete the winner's)."""
        raise NotImplementedError
