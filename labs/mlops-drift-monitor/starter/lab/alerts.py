"""Alert hysteresis (starter)."""

from __future__ import annotations


class HysteresisAlert:
    """Fire after ``fire_after`` consecutive breaches; clear after ``clear_after`` consecutive healthy checks.

    Why: a metric hovering around its threshold would otherwise flap the alert on and off every window.
    """

    def __init__(self, fire_after: int = 3, clear_after: int = 3) -> None:
        """TODO: ``ValueError`` when either number is < 1; start not firing with both streak counters at 0."""
        raise NotImplementedError("TODO: HysteresisAlert.__init__")

    @property
    def firing(self) -> bool:
        raise NotImplementedError("TODO: firing")

    def update(self, breached: bool) -> bool:
        """Feed one observation and return whether the alert is firing afterwards.

        TODO: a breach increments the breach streak and zeroes the healthy streak (and vice versa). When not firing,
        reaching ``fire_after`` breaches starts firing; when firing, reaching ``clear_after`` healthy observations stops it.
        """
        raise NotImplementedError("TODO: update")
