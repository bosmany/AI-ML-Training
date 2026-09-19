"""Rolling window of the most recent rows (starter)."""

from __future__ import annotations

from typing import Any


class RollingWindow:
    def __init__(self, max_rows: int) -> None:
        """TODO: ``ValueError`` if ``max_rows < 1``. Hint: ``collections.deque(maxlen=max_rows)`` evicts the oldest for you."""
        raise NotImplementedError("TODO: RollingWindow.__init__")

    def add(self, rows: list[dict[str, Any]]) -> None:
        """Append rows; keep only the newest ``max_rows`` (a single batch may be larger than the whole window)."""
        raise NotImplementedError("TODO: add")

    def __len__(self) -> int:
        raise NotImplementedError("TODO: __len__")

    def values(self, feature: str) -> list[Any]:
        """The feature's values currently in the window, oldest first."""
        raise NotImplementedError("TODO: values")
