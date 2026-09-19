"""PSI / KS / chi-square on hand-built arrays (no randomness)."""

from __future__ import annotations

import math

import pytest
from scipy import stats as scipy_stats

from lab.stats import chi_square_test, ks_test, psi, psi_edges


def test_psi_of_a_sample_against_itself_is_zero():
    values = [float(v) for v in range(1, 101)]
    assert psi(values, values, n_bins=10) == pytest.approx(0.0, abs=1e-12)


def test_psi_matches_the_hand_computed_value():
    # reference [1,2,3,4], 2 bins split at the median 2.5 -> expected 50% / 50%
    # current   [1,3,3,3] -> actual 25% / 75%;  PSI = (.25-.5)ln(.25/.5) + (.75-.5)ln(.75/.5) = .25*ln 3
    assert psi([1, 2, 3, 4], [1, 3, 3, 3], n_bins=2) == pytest.approx(0.25 * math.log(3), rel=1e-9)


def test_psi_uses_quantile_bins_of_the_reference_not_equal_width_bins():
    skewed_reference = [1, 1, 1, 1, 1, 1, 2, 3, 100, 1000]
    edges = psi_edges(skewed_reference, n_bins=4)
    assert list(edges) == sorted(set(edges)), "edges must be strictly increasing (ties collapsed)"
    assert edges[-1] < 100, "quantile edges follow the data (equal-width bins would put an edge near 250)"


def test_psi_bins_are_closed_on_the_right_a_value_equal_to_an_edge_belongs_to_the_lower_bin():
    # reference [1,2,3] with 2 bins -> the single edge is the median 2.0; bins are (-inf, 2] and (2, inf)
    # expected = [2/3, 1/3]; current [2,2,2,3] -> actual = [3/4, 1/4]
    expected, actual = [2 / 3, 1 / 3], [0.75, 0.25]
    hand = sum((a - e) * math.log(a / e) for a, e in zip(actual, expected, strict=True))
    assert psi([1, 2, 3], [2, 2, 2, 3], n_bins=2) == pytest.approx(hand, rel=1e-9)


def test_psi_with_an_empty_bin_uses_epsilon_instead_of_blowing_up():
    # every current value lands in the first bin -> the second bin has actual 0%
    value = psi([1, 2, 3, 4], [1, 1, 1, 1], n_bins=2, epsilon=1e-4)
    expected = (1 - 0.5) * math.log(1 / 0.5) + (1e-4 - 0.5) * math.log(1e-4 / 0.5)
    assert math.isfinite(value) and value == pytest.approx(expected, rel=1e-9)


def test_psi_with_many_ties_in_the_reference_is_finite_and_zero_for_the_same_distribution():
    reference = [0] * 50 + [1] * 50  # quantile edges collapse to [0, 1]
    assert psi(reference, list(reference), n_bins=10) == pytest.approx(0.0, abs=1e-12)
    shifted = psi(reference, [0] * 10 + [1] * 10 + [5] * 30, n_bins=10)
    assert math.isfinite(shifted) and shifted > 0.25, "a brand-new value range must register as drift"


def test_psi_counts_values_outside_the_reference_range_in_the_outer_bins():
    reference = [10, 20, 30, 40]
    for far_away in ([1000] * 4, [-1000] * 4):  # nothing may be silently dropped by the outermost bins
        value = psi(reference, far_away, n_bins=2)
        assert math.isfinite(value) and value > 1.0, f"all-outside sample {far_away[:1]} must be huge drift, got {value}"
    assert psi(reference, [-1000, -1000, 1000, 1000], n_bins=2) == pytest.approx(0.0, abs=1e-12), "50/50 split = reference"


def test_psi_ignores_nan_and_rejects_empty_input():
    reference = [float(v) for v in range(1, 21)]
    current = [3.0, 4.0, 5.0, 15.0, 16.0]
    assert psi(reference, current + [math.nan], n_bins=4) == pytest.approx(psi(reference, current, n_bins=4))
    with pytest.raises(ValueError):
        psi(reference, [], n_bins=4)
    with pytest.raises(ValueError):
        psi(reference, [math.nan, math.nan], n_bins=4)


def test_ks_test_wraps_scipys_two_sample_test():
    reference, current = list(range(1, 11)), list(range(6, 16))
    result = ks_test(reference, current)
    expected = scipy_stats.ks_2samp(reference, current)
    assert result.statistic == pytest.approx(0.5)
    assert result.statistic == pytest.approx(expected.statistic) and result.pvalue == pytest.approx(expected.pvalue)
    identical = ks_test(reference, list(reference))
    assert identical.statistic == 0.0 and identical.pvalue == pytest.approx(1.0)
    disjoint = ks_test(reference, [100 + v for v in reference])
    assert disjoint.statistic == 1.0 and disjoint.pvalue < 0.001


def test_chi_square_matches_the_hand_computed_statistic():
    # counts  A:50 B:50  vs  A:80 B:20 -> expected 65/35 in each row -> chi2 = 2*(15^2/65 + 15^2/35) = 19.78
    reference, current = ["A"] * 50 + ["B"] * 50, ["A"] * 80 + ["B"] * 20
    result = chi_square_test(reference, current)
    assert result.statistic == pytest.approx(2 * (225 / 65 + 225 / 35), rel=1e-9)
    assert result.dof == 1 and result.pvalue < 0.001


def test_chi_square_handles_identical_unseen_and_single_categories():
    same = chi_square_test(["a"] * 30 + ["b"] * 20, ["a"] * 6 + ["b"] * 4)
    assert same.statistic == pytest.approx(0.0, abs=1e-12) and same.pvalue == pytest.approx(1.0)

    unseen = chi_square_test(["a"] * 30 + ["b"] * 20, ["a"] * 10 + ["b"] * 5 + ["NEW"] * 15)
    assert unseen.dof == 2 and unseen.pvalue < 0.01, "a category that never appeared in training is drift"

    only_one = chi_square_test(["a"] * 10, ["a"] * 5)
    assert (only_one.statistic, only_one.pvalue, only_one.dof) == (0.0, 1.0, 0)
    with pytest.raises(ValueError):
        chi_square_test(["a"], [])
