"""Retry with exponential backoff and full jitter (injectable sleep and rng)."""
from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def retry_with_backoff(
    fn: Callable[[], T],
    *,
    attempts: int = 5,
    base: float = 0.5,
    cap: float = 30.0,
    retry_on: tuple[type[BaseException], ...] = (OSError,),
    sleep: Callable[[float], None] = time.sleep,
    rng: Callable[[], float] = random.random,
) -> T:
    """Call ``fn`` up to ``attempts`` times.

    Delay before retry n (n = 0, 1, ...) is ``rng() * min(cap, base * 2**n)`` ("full jitter": spreads out many
    clients that failed at the same moment). Only exceptions in ``retry_on`` are retried; the last one is
    re-raised when attempts run out, with no sleep after the final attempt.
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    for n in range(attempts):
        try:
            return fn()
        except retry_on:
            if n == attempts - 1:
                raise
            sleep(rng() * min(cap, base * 2**n))
    raise AssertionError("unreachable")  # pragma: no cover
