"""Deflated Sharpe Ratio and multiple testing correction.

Implements:
1. Deflated Sharpe Ratio (DSR) - accounts for multiple testing
2. Bonferroni correction
3. False Discovery Rate (FDR) control
4. Sharpe Ratio significance test

Based on:
- Bailey & Lopez de Prado (2014) "The Deflated Sharpe Ratio"
- Harvey & Liu (2015) "Backtesting"
"""

from __future__ import annotations

import math
from typing import Any


def _norm_cdf(x: float) -> float:
    """Standard normal CDF approximation."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _norm_ppf(p: float) -> float:
    """Standard normal inverse CDF (percent point function) approximation."""
    # Rational approximation for the inverse normal CDF
    if p <= 0:
        return -6.0
    if p >= 1:
        return 6.0

    # Coefficients for the rational approximation
    a = [
        -3.969683028665376e+01, 2.209460984245205e+02,
        -2.759285104469687e+02, 1.383577518672690e+02,
        -3.066479806614716e+01, 2.506628277459239e+00,
    ]
    b = [
        -5.447609879822406e+01, 1.615858368580409e+02,
        -1.556989798598866e+02, 6.680131188771972e+01,
        -1.328068155288572e+01,
    ]
    c = [
        -7.784894002430293e-03, -3.223964580411365e-01,
        -2.400758277161838e+00, -2.549732539343734e+00,
        4.374664141464968e+00, 2.938163982698783e+00,
    ]
    d = [
        7.784695709041462e-03, 3.224671290700398e-01,
        2.445134137142996e+00, 3.754408661907416e+00,
    ]

    p_low = 0.02425
    p_high = 1 - p_low
    q: float
    r: float

    if p < p_low:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    elif p <= p_high:
        q = p - 0.5
        r = q * q
        return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
               (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    else:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)


def deflated_sharpe_ratio(
    sharpe_observed: float,
    n_trials: int,
    n_observations: int,
    sharpe_max: float = 0.0,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
) -> dict[str, Any]:
    """Compute the Deflated Sharpe Ratio (DSR).

    The DSR adjusts the observed Sharpe Ratio for multiple testing,
    accounting for the fact that some strategies will appear profitable
    purely by chance.

    Args:
        sharpe_observed: The observed Sharpe Ratio of the strategy
        n_trials: Number of strategies/trials tested (multiple testing)
        n_observations: Number of return observations used to compute Sharpe
        sharpe_max: Maximum Sharpe Ratio among all tested strategies
        skewness: Skewness of the return distribution
        kurtosis: Excess kurtosis of the return distribution (3 = normal)

    Returns:
        Dict with DSR, p-value, and significance information
    """
    if n_trials <= 0 or n_observations <= 0:
        return {
            "deflated_sharpe": 0.0,
            "p_value": 1.0,
            "significant_95": False,
            "significant_99": False,
            "n_trials": n_trials,
            "warning": "Invalid inputs",
        }

    # Expected maximum Sharpe under null hypothesis (no skill)
    # Bailey & Lopez de Prado (2014) formula

    # Expected max of n_trials independent standard normals
    e_max = math.sqrt(2 * math.log(n_trials)) - \
            (math.log(math.pi) + math.log(math.log(n_trials))) / \
            (2 * math.sqrt(2 * math.log(n_trials)))

    # Adjust for non-normal returns using skewness and kurtosis
    # Harvey & Liu (2015) adjustment
    if skewness != 0 or kurtosis != 3:
        adjustment = (skewness / 6) * e_max**2 + \
                     ((kurtosis - 3) / 24) * (e_max**3 - 3*e_max) - \
                     (skewness**2 / 36) * (2*e_max**3 - 5*e_max)
        e_max += adjustment

    # Standard error of Sharpe Ratio
    sr_se = math.sqrt(
        (1 + 0.5 * sharpe_observed**2 - skewness * sharpe_observed +
         (kurtosis - 3) / 4 * sharpe_observed**2) / max(n_observations - 1, 1)
    )

    # Test statistic
    z = (sharpe_observed - e_max) / sr_se if sr_se > 0 else 0.0

    # P-value (two-tailed)
    p_value = 2 * (1 - _norm_cdf(abs(z)))

    # Deflated Sharpe Ratio
    dsr = _norm_cdf(z)

    return {
        "deflated_sharpe": round(dsr, 4),
        "p_value": round(p_value, 6),
        "significant_95": p_value < 0.05,
        "significant_99": p_value < 0.01,
        "n_trials": n_trials,
        "expected_max_sharpe": round(e_max, 4),
        "sharpe_se": round(sr_se, 4),
        "z_score": round(z, 4),
    }


def sharpe_ratio_significance(
    sharpe: float,
    n_observations: int,
    risk_free_rate: float = 0.0,
) -> dict[str, Any]:
    """Test if a Sharpe Ratio is statistically significant.

    Tests H0: Sharpe = 0 vs H1: Sharpe > 0

    Args:
        sharpe: Observed Sharpe Ratio
        n_observations: Number of return observations
        risk_free_rate: Risk-free rate (annualized)

    Returns:
        Dict with significance test results
    """
    if n_observations <= 2:
        return {
            "significant": False,
            "p_value": 1.0,
            "warning": "Too few observations",
        }

    # Standard error of Sharpe (assuming normal returns)
    sr_se = math.sqrt((1 + 0.5 * sharpe**2) / max(n_observations - 1, 1))

    # T-statistic
    t_stat = sharpe / sr_se if sr_se > 0 else 0.0

    # Approximate p-value using normal distribution (large sample)
    p_value = 2 * (1 - _norm_cdf(abs(t_stat)))

    return {
        "significant_95": p_value < 0.05,
        "significant_99": p_value < 0.01,
        "p_value": round(p_value, 6),
        "t_statistic": round(t_stat, 4),
        "sharpe_se": round(sr_se, 4),
    }


def multiple_testing_correction(
    p_values: list[float],
    method: str = "bonferroni",
) -> dict[str, Any]:
    """Apply multiple testing correction to a list of p-values.

    Args:
        p_values: List of p-values from multiple tests
        method: Correction method ('bonferroni', 'holm', 'fdr_bh')

    Returns:
        Dict with adjusted p-values and significance flags
    """
    n = len(p_values)
    if n == 0:
        return {"adjusted_p_values": [], "significant": []}

    if method == "bonferroni":
        adjusted = [min(p * n, 1.0) for p in p_values]
    elif method == "holm":
        # Holm-Bonferroni step-down procedure
        sorted_idx = sorted(range(n), key=lambda i: p_values[i])
        adjusted = [1.0] * n
        for rank, idx in enumerate(sorted_idx):
            adjusted[idx] = min(p_values[idx] * (n - rank), 1.0)
        # Ensure monotonicity
        for i in range(1, n):
            idx = sorted_idx[i]
            prev_idx = sorted_idx[i-1]
            adjusted[idx] = max(adjusted[idx], adjusted[prev_idx])
    elif method == "fdr_bh":
        # Benjamini-Hochberg FDR control
        sorted_idx = sorted(range(n), key=lambda i: p_values[i])
        adjusted = [1.0] * n
        for rank, idx in enumerate(sorted_idx):
            adjusted[idx] = min(p_values[idx] * n / (rank + 1), 1.0)
        # Ensure monotonicity (from largest to smallest)
        for i in range(n - 2, -1, -1):
            idx = sorted_idx[i]
            next_idx = sorted_idx[i+1]
            adjusted[idx] = min(adjusted[idx], adjusted[next_idx])
    else:
        adjusted = list(p_values)

    significant_95 = [p < 0.05 for p in adjusted]
    significant_99 = [p < 0.01 for p in adjusted]

    return {
        "adjusted_p_values": [round(p, 6) for p in adjusted],
        "significant_95": significant_95,
        "significant_99": significant_99,
        "n_significant_95": sum(significant_95),
        "n_significant_99": sum(significant_99),
        "method": method,
    }
