"""Exceptions (scaffold - provided)."""

from __future__ import annotations


class LabError(Exception):
    """Base class: the CLI turns any LabError into ``error: <message>`` and exit code 1."""


class RunNotFoundError(LabError):
    pass


class RunStateError(LabError):
    """Operation not allowed in the run's current state (e.g. logging to a finished run)."""


class ImmutableParamError(LabError):
    """A parameter was logged again with a different value."""


class RegistryError(LabError):
    pass


class ModelVersionNotFoundError(RegistryError):
    pass


class LineageError(RegistryError):
    """The run cannot be registered because its dataset hash or code version is missing."""


class InvalidTransitionError(RegistryError):
    pass


class RollbackError(RegistryError):
    pass


class PromotionBlockedError(RegistryError):
    """Promotion gates failed. ``reasons`` lists EVERY failed gate, not just the first."""

    def __init__(self, reasons: list[str]) -> None:
        super().__init__("promotion blocked: " + "; ".join(reasons))
        self.reasons = reasons
