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

    TODO:
    - attempts < 1 -> ValueError
    - delay before retry n (n = 0, 1, ...) is ``rng() * min(cap, base * 2**n)``  ("full jitter")
    - only exceptions in ``retry_on`` are retried; anything else propagates immediately
    - when attempts run out re-raise the LAST error, with no sleep after the final attempt
    """
    raise NotImplementedError
