"""Configuration objects (scaffold - provided, do not edit)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    kind: Literal["numeric", "categorical"]


@dataclass(frozen=True)
class MonitorConfig:
    """Everything the monitor needs. ``reference`` holds the training-time values of every feature."""

    reference: Mapping[str, Sequence[Any]]
    features: tuple[FeatureSpec, ...]
    window_size: int = 500  # rows kept in the rolling window
    min_window_rows: int = 30  # do not evaluate drift on fewer rows than this (too noisy)
    n_bins: int = 10  # PSI quantile bins
    epsilon: float = 1e-4  # PSI proportion floor for empty bins
    psi_threshold: float = 0.2  # numeric feature is "breached" when PSI >= this
    psi_critical: float = 0.3  # a FIRING numeric feature with PSI >= this recommends retraining on its own
    chi2_alpha: float = 0.01  # categorical feature is "breached" when the chi-square p-value < this
    ks_alpha: float = 0.01  # reported for information (KS is very sensitive on big windows)
    fire_after: int = 3  # consecutive breached evaluations before an alert fires
    clear_after: int = 3  # consecutive healthy evaluations before it clears

    def __post_init__(self) -> None:
        if self.window_size < 1 or self.min_window_rows < 1 or self.min_window_rows > self.window_size:
            raise ValueError("need 1 <= min_window_rows <= window_size")
        for spec in self.features:
            if len(self.reference.get(spec.name, ())) == 0:
                raise ValueError(f"reference data for feature {spec.name!r} is missing or empty")
