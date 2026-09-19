"""The drift monitor: validation, rolling window, per-feature evaluation, alerts, recommendation (starter)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lab.alerts import HysteresisAlert  # noqa: F401
from lab.config import FeatureSpec, MonitorConfig
from lab.schemas import FeatureDrift
from lab.stats import chi_square_test, ks_test, psi  # noqa: F401
from lab.windows import RollingWindow  # noqa: F401

MAX_REPORTED_PROBLEMS = 20


class BatchValidationError(ValueError):
    """Raised by ``ingest`` for an invalid batch; ``problems`` is the list of messages."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass
class IngestSummary:
    accepted: int
    window_rows: int
    evaluated: bool
    results: dict[str, FeatureDrift] = field(default_factory=dict)
    alerting: list[str] = field(default_factory=list)


class DriftMonitor:
    def __init__(self, config: MonitorConfig) -> None:
        """TODO: keep ``config``; create a ``RollingWindow(config.window_size)``; one ``HysteresisAlert(fire_after,
        clear_after)`` per feature (dict by name); ``self.latest: dict[str, FeatureDrift] = {}``."""
        raise NotImplementedError("TODO: DriftMonitor.__init__")

    def validate_batch(self, rows: list[dict[str, Any]]) -> list[str]:
        """Problems found in the batch, as messages (empty list = valid). Extra columns are fine.

        TODO: for every row and configured feature report ``"row {i}: missing feature '{name}'"`` when the key is
        absent or None; numeric features must be int/float, NOT bool, and finite ("row 3: 'age' must be a finite number,
        got 'old'"); categorical features must be str or int (not bool). Return at most ``MAX_REPORTED_PROBLEMS``.
        """
        raise NotImplementedError("TODO: validate_batch")

    def ingest(self, rows: list[dict[str, Any]]) -> IngestSummary:
        """Validate, add to the window and, once it holds ``config.min_window_rows`` rows, evaluate every feature.

        TODO: invalid batch -> ``BatchValidationError(problems)`` and NOTHING changes (no partial ingestion).
        Below ``min_window_rows`` return ``IngestSummary(len(rows), len(window), evaluated=False)`` WITHOUT touching the
        alerts. Otherwise evaluate each feature on ``window.values(name)`` vs ``config.reference[name]``:
        - numeric: ``psi(..., n_bins=config.n_bins, epsilon=config.epsilon)`` + ``ks_test``; breached = psi >= psi_threshold
        - categorical: ``chi_square_test``; breached = pvalue < chi2_alpha
        then ``alert.update(breached)`` -> ``FeatureDrift(...)``. Store them in ``self.latest``.
        """
        raise NotImplementedError("TODO: ingest")

    def alerting_features(self) -> list[str]:
        """Names of the features whose alert is currently firing (config order)."""
        raise NotImplementedError("TODO: alerting_features")

    def recommendation(self) -> dict[str, Any]:
        """``{"action": "retrain" | "investigate" | "none", "reasons": [str, ...]}``.

        TODO: ``retrain`` when 2 or more features are firing, or when one FIRING numeric feature has
        ``psi >= config.psi_critical``; ``investigate`` when exactly one (non-critical) feature is firing; else ``none``
        with no reasons.
        """
        raise NotImplementedError("TODO: recommendation")

    def status(self) -> dict[str, Any]:
        """JSON-ready dict: ``ready`` (has the window ever been evaluated), ``window_rows``, ``window_size``,
        ``features`` ({name: FeatureDrift.to_dict()} from ``self.latest``), ``alerting``, ``recommendation``."""
        raise NotImplementedError("TODO: status")
