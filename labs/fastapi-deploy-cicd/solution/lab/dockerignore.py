"""Minimal ``.dockerignore`` handling: parse patterns and decide whether a path is excluded."""

from __future__ import annotations

import re
from functools import lru_cache

from lab.errors import AssetError


def parse_dockerignore(text: str) -> list[str]:
    """Return the non-empty, non-comment lines. Raises ``AssetError`` if there are none."""
    patterns = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
    if not patterns:
        raise AssetError(".dockerignore has no patterns - add the things that must not enter the build context")
    return patterns


@lru_cache(maxsize=256)
def _to_regex(pattern: str) -> re.Pattern[str]:
    pattern = pattern.strip("/") if pattern != "/" else pattern
    out = ""
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pattern.startswith("**", i):
            out += ".*"
            i += 2
        elif char == "*":
            out += "[^/]*"
            i += 1
        elif char == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(char)
            i += 1
    return re.compile(f"^{out}(?:/.*)?$")  # a match on a directory also excludes everything below it


def is_ignored(patterns: list[str], path: str) -> bool:
    """Does the Docker build context exclude ``path`` (relative, ``/`` separated)? Last match wins,
    ``!pattern`` re-includes, patterns are anchored at the context root (like Docker's)."""
    path = path.strip("/")
    ignored = False
    for pattern in patterns:
        negate = pattern.startswith("!")
        body = pattern[1:] if negate else pattern
        if _to_regex(body).match(path):
            ignored = not negate
    return ignored
