"""HTTP schemas and the per-feature result record (scaffold - provided, do not edit)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    """A batch of logged predictions: one dict per row, feature values plus any extra columns (e.g. "prediction")."""

    rows: list[dict[str, Any]] = Field(min_length=1)


class IngestResponse(BaseModel):
    accepted: int
    window_rows: int
    evaluated: bool
    alerting: list[str]


@dataclass(frozen=True)
class FeatureDrift:
    """Drift measurements of ONE feature over the current window. Fields not relevant to the kind are None."""

    feature: str
    kind: str
    breached: bool  # this evaluation crossed the threshold
    alerting: bool  # the hysteresis alert is currently firing
    psi: float | None = None
    ks_statistic: float | None = None
    ks_pvalue: float | None = None
    chi2_statistic: float | None = None
    chi2_pvalue: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "breached": self.breached,
            "alerting": self.alerting,
            "psi": self.psi,
            "ks_statistic": self.ks_statistic,
            "ks_pvalue": self.ks_pvalue,
            "chi2_statistic": self.chi2_statistic,
            "chi2_pvalue": self.chi2_pvalue,
        }
