"""Filesystem safety: guarded deletes, atomic manifest writes and a lock file."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any


class UnsafePathError(ValueError):
    """A path resolves outside the target directory (``..`` traversal or a symlink)."""


class LockHeldError(RuntimeError):
    """Another run holds the lock."""


def safe_delete(target: Path, path: Path) -> None:
    """Delete ``path`` (file, symlink or directory tree) ONLY if it lives inside ``target``.

    Uses ``resolve()`` so that ``target/../x`` and ``target/linkdir/file`` are refused, and refuses symlinks
    outright (a retention tool has no business following or removing them). Note: a check-then-delete
    sequence still has a tiny race window if an attacker can swap directories concurrently; the scan never
    yields symlinks, and the lock stops concurrent janitors.
    """
    root = target.resolve()
    if path.is_symlink():
        raise UnsafePathError(f"refusing to delete symlink {path}")
    resolved = path.resolve()
    if resolved == root or not resolved.is_relative_to(root):
        raise UnsafePathError(f"refusing to delete {path}: resolves to {resolved}, outside {root}")
    if resolved.is_dir():
        shutil.rmtree(resolved)
    else:
        resolved.unlink()


def write_manifest_atomic(path: Path, data: dict[str, Any]) -> None:
    """Write JSON so a reader (or a crash) never sees a half-written file: temp file + fsync + os.replace."""
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


class FileLock:
    """Exclusive lock via ``O_CREAT | O_EXCL`` - atomic even over NFS-less local disks; no check-then-create race."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._held = False

    def __enter__(self) -> FileLock:
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            try:
                owner = self.path.read_text().strip()
            except OSError:
                owner = "?"
            raise LockHeldError(f"{self.path} is held by pid {owner or '?'}; remove it if that process is gone") from None
        with os.fdopen(fd, "w") as fh:
            fh.write(str(os.getpid()))
        self._held = True
        return self

    def __exit__(self, *exc: object) -> None:
        if self._held:
            self.path.unlink(missing_ok=True)
            self._held = False
