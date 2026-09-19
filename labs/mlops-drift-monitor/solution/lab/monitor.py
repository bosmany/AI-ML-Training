"""The drift monitor: validation, rolling window, per-feature evaluation, alerts, recommendation (reference solution)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from lab.alerts import HysteresisAlert
from lab.config import FeatureSpec, MonitorConfig
from lab.schemas import FeatureDrift
from lab.stats import chi_square_test, ks_test, psi
from lab.windows import RollingWindow

MAX_REPORTED_PROBLEMS = 20


class BatchValidationError(ValueError):
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
        self.config = config
        self.window = RollingWindow(config.window_size)
        self.alerts = {s.name: HysteresisAlert(config.fire_after, config.clear_after) for s in config.features}
        self.latest: dict[str, FeatureDrift] = {}

    # ------------------------------------------------------------------ validation
    def validate_batch(self, rows: list[dict[str, Any]]) -> list[str]:
        """Human-readable problems (empty list = the batch is fine). Extra columns are allowed."""
        problems: list[str] = []
        for index, row in enumerate(rows):
            for spec in self.config.features:
                if spec.name not in row or row[spec.name] is None:
                    problems.append(f"row {index}: missing feature '{spec.name}'")
                    continue
                value = row[spec.name]
                if spec.kind == "numeric":
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                        problems.append(f"row {index}: '{spec.name}' must be a finite number, got {value!r}")
                elif not isinstance(value, (str, int)) or isinstance(value, bool):
                    problems.append(f"row {index}: '{spec.name}' must be a string category, got {value!r}")
        return problems[:MAX_REPORTED_PROBLEMS]

    # ------------------------------------------------------------------ ingest / evaluate
    def ingest(self, rows: list[dict[str, Any]]) -> IngestSummary:
        """Validate, add to the window and (once the window is big enough) evaluate every feature.

        An invalid batch raises ``BatchValidationError`` and changes NOTHING (no partial ingestion).
        """
        problems = self.validate_batch(rows)
        if problems:
            raise BatchValidationError(problems)
        self.window.add(rows)
        if len(self.window) < self.config.min_window_rows:
            return IngestSummary(len(rows), len(self.window), False)
        results = {spec.name: self._evaluate(spec) for spec in self.config.features}
        self.latest = results
        return IngestSummary(len(rows), len(self.window), True, results, self.alerting_features())

    def _evaluate(self, spec: FeatureSpec) -> FeatureDrift:
        cfg = self.config
        current = self.window.values(spec.name)
        reference = cfg.reference[spec.name]
        if spec.kind == "numeric":
            value = psi(reference, current, n_bins=cfg.n_bins, epsilon=cfg.epsilon)
            ks = ks_test(reference, current)
            breached = value >= cfg.psi_threshold
            firing = self.alerts[spec.name].update(breached)
            return FeatureDrift(spec.name, "numeric", breached, firing, psi=value, ks_statistic=ks.statistic, ks_pvalue=ks.pvalue)
        chi = chi_square_test(reference, current)
        breached = chi.pvalue < cfg.chi2_alpha
        firing = self.alerts[spec.name].update(breached)
        return FeatureDrift(spec.name, "categorical", breached, firing, chi2_statistic=chi.statistic, chi2_pvalue=chi.pvalue)

    def alerting_features(self) -> list[str]:
        return [name for name, alert in self.alerts.items() if alert.firing]

    # ------------------------------------------------------------------ status
    def recommendation(self) -> dict[str, Any]:
        """``retrain`` when 2+ features are firing or one firing numeric feature has PSI >= psi_critical;
        ``investigate`` when exactly one feature is firing; otherwise ``none``."""
        firing = self.alerting_features()
        critical = [
            name
            for name in firing
            if (self.latest[name].psi or 0.0) >= self.config.psi_critical and self.latest[name].kind == "numeric"
        ]
        if len(firing) >= 2:
            return {"action": "retrain", "reasons": [f"{len(firing)} features are drifting: {', '.join(firing)}"]}
        if critical:
            return {"action": "retrain", "reasons": [f"{critical[0]} PSI {self.latest[critical[0]].psi:.3f} >= critical {self.config.psi_critical}"]}
        if firing:
            return {"action": "investigate", "reasons": [f"{firing[0]} is drifting (alert firing)"]}
        return {"action": "none", "reasons": []}

    def status(self) -> dict[str, Any]:
        return {
            "ready": bool(self.latest),
            "window_rows": len(self.window),
            "window_size": self.config.window_size,
            "features": {name: result.to_dict() for name, result in self.latest.items()},
            "alerting": self.alerting_features(),
            "recommendation": self.recommendation(),
        }
