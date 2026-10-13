"""Behavioral regression tests for :func:`deflated_sharpe_ratio`.

Covers TD-01: the degenerate ``n_trials <= 1`` case, where the Bailey &
Lopez de Prado expected-maximum-Sharpe term collapses (``log(1) == 0``) and
previously raised ``ValueError: math domain error``.

Tests are behavioral: they call the public function and assert on the returned
mapping / raised exceptions — no source-code inspection or regex matching.
"""

from __future__ import annotations

import math

import pytest

from backtesting.metrics.deflated_sharpe import deflated_sharpe_ratio


def test_dsr_handles_single_trial():
    """``n_trials=1`` must not raise and must return a valid DSR in [0, 1]."""
    result = deflated_sharpe_ratio(
        sharpe_observed=1.5,
        n_trials=1,
        n_observations=250,
        sharpe_max=1.5,
    )

    # Degenerate guard must not fall back to the "Invalid inputs" early return.
    assert "warning" not in result or result["warning"] != "Invalid inputs"

    # With a single trial there is no multiple-testing deflation, so the
    # expected maximum Sharpe under the null is the mean of one standard
    # normal: exactly 0.
    assert result["expected_max_sharpe"] == pytest.approx(0.0)

    assert 0.0 <= result["deflated_sharpe"] <= 1.0
    assert 0.0 <= result["p_value"] <= 1.0
    assert result["n_trials"] == 1
    assert result["significant_95"] in (True, False)
    assert math.isfinite(result["deflated_sharpe"])
    assert math.isfinite(result["p_value"])


def test_dsr_single_trial_has_no_deflation_vs_raw_significance():
    """Single-trial DSR equals the undeflated significance of the Sharpe."""
    result = deflated_sharpe_ratio(
        sharpe_observed=2.0,
        n_trials=1,
        n_observations=500,
    )

    # z = (sharpe - e_max) / sr_se with e_max == 0 => DSR = Phi(sharpe / sr_se).
    sr_se = result["sharpe_se"]
    assert sr_se > 0
    expected_dsr = 0.5 * (1 + math.erf((2.0 / sr_se) / math.sqrt(2)))
    assert result["deflated_sharpe"] == pytest.approx(expected_dsr, abs=1e-3)


def test_dsr_negative_sharpe_single_trial_yields_low_dsr():
    """A losing strategy with one trial yields a low DSR, with no exception.

    ``deflated_sharpe`` (= Phi(z)) is the probability that the true Sharpe
    exceeds the null benchmark, so a loser maps close to 0. Note that
    ``significant_95`` is a *two-tailed* test of "Sharpe != 0", so a strongly
    negative Sharpe is legitimately flagged significant.
    """
    result = deflated_sharpe_ratio(
        sharpe_observed=-1.2,
        n_trials=1,
        n_observations=250,
    )

    assert 0.0 <= result["deflated_sharpe"] <= 1.0
    assert result["deflated_sharpe"] < 0.5
    assert result["p_value"] < 0.05  # far from zero, in the negative direction
    assert result["expected_max_sharpe"] == pytest.approx(0.0)


def test_dsr_zero_or_negative_trials_still_guarded():
    """The pre-existing invalid-input guard for ``n_trials <= 0`` is intact."""
    for trials in (0, -5):
        result = deflated_sharpe_ratio(
            sharpe_observed=1.0,
            n_trials=trials,
            n_observations=250,
        )
        assert result["warning"] == "Invalid inputs"
        assert result["deflated_sharpe"] == 0.0
        assert result["p_value"] == 1.0


def test_dsr_multi_trial_path_unchanged():
    """Multiple trials still produce a finite, deflated result (no regression)."""
    result = deflated_sharpe_ratio(
        sharpe_observed=1.5,
        n_trials=100,
        n_observations=250,
    )

    assert math.isfinite(result["expected_max_sharpe"])
    assert result["expected_max_sharpe"] > 0
    assert 0.0 <= result["deflated_sharpe"] <= 1.0
    assert result["n_trials"] == 100
