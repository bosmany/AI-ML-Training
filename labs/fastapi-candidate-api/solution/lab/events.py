"""Tiny in-process event log used by the background-task exercise (scaffold - provided)."""

from __future__ import annotations

from typing import Any


def record_event(events: list[dict[str, Any]], name: str, **payload: Any) -> None:
    """Append ``{"name": name, **payload}`` to ``events``.

    Stands in for "send a Slack message / publish to a queue". Because it is only
    an append, tests can assert on it after the response has been sent.
    """
    events.append({"name": name, **payload})
