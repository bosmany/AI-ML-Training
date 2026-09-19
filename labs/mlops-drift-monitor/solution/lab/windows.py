"""Rolling window of recent rows (reference solution)."""

from __future__ import annotations

from collections import deque
from typing import Any


class RollingWindow:
    def __init__(self, max_rows: int) -> None:
        if max_rows < 1:
            raise ValueError("max_rows must be >= 1")
        self.max_rows = max_rows
        self._rows: deque[dict[str, Any]] = deque(maxlen=max_rows)  # deque drops the oldest automatically

    def add(self, rows: list[dict[str, Any]]) -> None:
        self._rows.extend(rows)

    def __len__(self) -> int:
        return len(self._rows)

    def values(self, feature: str) -> list[Any]:
        """The feature's values in the window, oldest first."""
        return [row[feature] for row in self._rows]
