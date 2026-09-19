"""Drift statistics (reference solution)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy import stats as scipy_stats


@dataclass(frozen=True)
class KSResult:
    statistic: float
    pvalue: float


@dataclass(frozen=True)
class ChiSquareResult:
    statistic: float
    pvalue: float
    dof: int


def _finite(values: Sequence[float], label: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]  # NaN / inf carry no distribution information
    if array.size == 0:
        raise ValueError(f"{label} has no finite values")
    return array


def psi_edges(reference: Sequence[float], n_bins: int = 10) -> np.ndarray:
    """Inner bin edges = interior quantiles of the reference. Duplicate edges (ties) are collapsed."""
    ref = _finite(reference, "reference")
    return np.unique(np.quantile(ref, np.linspace(0, 1, n_bins + 1)[1:-1]))


def _proportions(values: np.ndarray, edges: np.ndarray) -> np.ndarray:
    # bin i is (edges[i-1], edges[i]]; the first bin is open to -inf and the last to +inf so no value is lost
    index = np.searchsorted(edges, values, side="left")
    counts = np.bincount(index, minlength=len(edges) + 1)
    return counts / counts.sum()


def psi(reference: Sequence[float], current: Sequence[float], *, n_bins: int = 10, epsilon: float = 1e-4) -> float:
    """Population Stability Index of ``current`` against ``reference``.

    PSI = sum((actual% - expected%) * ln(actual% / expected%)) over quantile bins built from the reference.
    Empty bins would give ln(0) / division by zero, so proportions are floored at ``epsilon``.
    """
    edges = psi_edges(reference, n_bins)
    expected = np.maximum(_proportions(_finite(reference, "reference"), edges), epsilon)
    actual = np.maximum(_proportions(_finite(current, "current"), edges), epsilon)
    return float(np.sum((actual - expected) * np.log(actual / expected)))


def ks_test(reference: Sequence[float], current: Sequence[float]) -> KSResult:
    """Two-sample Kolmogorov-Smirnov test."""
    result = scipy_stats.ks_2samp(_finite(reference, "reference"), _finite(current, "current"))
    return KSResult(float(result.statistic), float(result.pvalue))


def chi_square_test(reference: Sequence[Any], current: Sequence[Any]) -> ChiSquareResult:
    """Chi-square test of homogeneity: do the two samples share one category distribution?

    Builds a 2 x k contingency table over the UNION of categories (a category unseen in the reference is a
    column with a zero in the reference row). No Yates correction. One category overall -> nothing to test.
    """
    if len(reference) == 0 or len(current) == 0:
        raise ValueError("both samples must be non-empty")
    ref_labels, cur_labels = [str(v) for v in reference], [str(v) for v in current]
    categories = sorted(set(ref_labels) | set(cur_labels))
    if len(categories) < 2:
        return ChiSquareResult(0.0, 1.0, 0)
    table = np.array(
        [[labels.count(c) for c in categories] for labels in (ref_labels, cur_labels)], dtype=float
    )
    statistic, pvalue, dof, _ = scipy_stats.chi2_contingency(table, correction=False)
    return ChiSquareResult(float(statistic), float(pvalue), int(dof))
