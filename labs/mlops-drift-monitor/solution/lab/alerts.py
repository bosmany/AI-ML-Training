"""Alert hysteresis (reference solution)."""

from __future__ import annotations


class HysteresisAlert:
    """Fire after ``fire_after`` consecutive breaches, clear after ``clear_after`` consecutive healthy checks.

    Stops a metric hovering around its threshold from flapping the alert on and off.
    """

    def __init__(self, fire_after: int = 3, clear_after: int = 3) -> None:
        if fire_after < 1 or clear_after < 1:
            raise ValueError("fire_after and clear_after must be >= 1")
        self.fire_after = fire_after
        self.clear_after = clear_after
        self._firing = False
        self._breaches = 0
        self._healthy = 0

    @property
    def firing(self) -> bool:
        return self._firing

    def update(self, breached: bool) -> bool:
        """Feed one observation; return whether the alert is firing afterwards."""
        if breached:
            self._breaches += 1
            self._healthy = 0
            if not self._firing and self._breaches >= self.fire_after:
                self._firing = True
        else:
            self._healthy += 1
            self._breaches = 0
            if self._firing and self._healthy >= self.clear_after:
                self._firing = False
        return self._firing
