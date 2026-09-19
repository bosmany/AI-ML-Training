"""Drift statistics (starter). Implement the four functions below with numpy + scipy."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy import stats as scipy_stats  # noqa: F401


@dataclass(frozen=True)
class KSResult:
    statistic: float
    pvalue: float


@dataclass(frozen=True)
class ChiSquareResult:
    statistic: float
    pvalue: float
    dof: int


def psi_edges(reference: Sequence[float], n_bins: int = 10) -> np.ndarray:
    """Inner bin edges: the interior quantiles of the reference.

    TODO: drop NaN/inf from the reference (``ValueError`` if nothing is left); take
    ``np.quantile(ref, np.linspace(0, 1, n_bins + 1)[1:-1])`` and collapse duplicates with ``np.unique`` (a reference
    full of ties would otherwise create zero-width bins).
    """
    raise NotImplementedError("TODO: psi_edges")


def psi(reference: Sequence[float], current: Sequence[float], *, n_bins: int = 10, epsilon: float = 1e-4) -> float:
    """Population Stability Index of ``current`` against ``reference``.

    PSI = sum((actual% - expected%) * ln(actual% / expected%)) over the reference's quantile bins.

    TODO:
    - bin i is ``(edges[i-1], edges[i]]``: ``np.searchsorted(edges, values, side="left")`` + ``np.bincount(...,
      minlength=len(edges) + 1)``. The first and last bins are open-ended so values outside the reference range still count.
    - proportions = counts / total; an empty bin would make ``ln(0)`` / divide by zero, so floor every proportion at
      ``epsilon`` (``np.maximum``).
    - drop NaN/inf from ``current`` (``ValueError`` when nothing remains).
    """
    raise NotImplementedError("TODO: psi")


def ks_test(reference: Sequence[float], current: Sequence[float]) -> KSResult:
    """Two-sample Kolmogorov-Smirnov test via ``scipy.stats.ks_2samp`` (drop non-finite values first)."""
    raise NotImplementedError("TODO: ks_test")


def chi_square_test(reference: Sequence[Any], current: Sequence[Any]) -> ChiSquareResult:
    """Chi-square test of homogeneity for categorical features.

    TODO: empty sample -> ``ValueError``. Build a 2 x k table of counts over the UNION of categories (a category the
    reference never saw is a column with 0 in the reference row - that IS drift). Fewer than 2 categories overall ->
    ``ChiSquareResult(0.0, 1.0, 0)``. Otherwise ``scipy.stats.chi2_contingency(table, correction=False)`` (no Yates
    correction, so the statistic is the textbook sum of (observed-expected)^2/expected).
    """
    raise NotImplementedError("TODO: chi_square_test")
