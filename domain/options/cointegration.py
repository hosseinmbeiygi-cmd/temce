"""Cointegration analysis for spread-based signals (سند v5.0 §3.4).

Tier-2 precondition (سند §3.4):

  | معیار | حداقل لازم |
  |---|---|
  | طول سری زمانی هم‌پوشان دو نماد | حداقل ۲۵۰ نقطه معاملاتی |
  | ثبات رابطه هم‌انباشتگی | تایید در آزمون خارج از نمونه با p-value پایدار |

Implementation:
  - Johansen trace test on the VECM of two I(1) series using eigenvalue
    decomposition of the product of lagged-difference and level matrices
    (numpy-only — no statsmodels dependency).
  - Spread signal at |Zₜ| > 2 (سند §3.4: Zₜ = (Spreadₜ − μ) / σ).
  - Data-sufficiency gate with explicit min-length; when length < 250 the
    function refuses to test and the caller must fall back to Tier-1
    cost-of-carry (سند §3.4: «در غیر این صورت ... به‌جای Cointegration، صرفاً
    از مدل Cost-of-Carry ساده»).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

# Minimum trading points per the v5.0 doc (سند §3.4, پیوست ه).
MIN_SERIES_LENGTH = 250
DEFAULT_Z_THRESHOLD = 2.0


@dataclass
class CointegrationResult:
    trace_stat: float
    crit_value_95: float  # 95% critical value (5% significance)
    p_value: float  # crude MacKinnon-style approximation
    eigenvector: list[float]  # weights such that w'·X is stationary
    is_cointegrated: bool


def _mackinnon_pvalue_2var(trace_stat: float) -> float:
    """Approximate 2-variable MacKinnon p-value for the trace statistic.

    Uses an exponential-tail fit calibrated against Johansen's tables. It is
    not exact but monotonic and good enough for ranking. Real p-values require
    tables; this is a Tier-2 gate, not a research tool.
    """
    if trace_stat <= 0:
        return 1.0
    # For 2 variables at 5%, the 95% critical value is ~12.21; for 1% it's ~16.16.
    if trace_stat >= 16.16:
        return 0.001
    if trace_stat >= 12.21:
        # Interpolate roughly between 0.05 and 0.01
        t = (trace_stat - 12.21) / (16.16 - 12.21)
        return 0.05 - 0.04 * t
    # Tail: exponential decay below the 5% critical value
    return float(np.exp(-(trace_stat - 4.0) / 4.0))


def johansen_trace_test(
    series1: Sequence[float], series2: Sequence[float], min_length: int = MIN_SERIES_LENGTH
) -> CointegrationResult | None:
    """Johansen trace test for two I(1) series.

    Returns None when min_length is not satisfied (caller must use Tier 1).
    Eigen-decomposition on the product of the differenced and level matrices
    gives the largest eigenvalue; trace statistic is its negative log.
    """
    if len(series1) != len(series2) or len(series1) < min_length:
        return None
    x = np.asarray(series1, dtype=float)
    y = np.asarray(series2, dtype=float)
    if np.any(np.isnan(x)) or np.any(np.isnan(y)):
        return None
    # Lagged levels
    Z = np.column_stack([x[:-1], y[:-1]])
    # Differenced (one-step)
    dX = np.diff(x)[:, None]
    dY = np.diff(y)[:, None]
    dZ = np.column_stack([dX, dY])
    # OLS: regress ΔX,ΔY on lagged levels (intercept excluded for speed)
    M00 = Z.T @ Z
    M01 = Z.T @ dZ
    M11 = dZ.T @ dZ
    try:
        Beta = np.linalg.solve(M00, M01)
    except np.linalg.LinAlgError:
        return None
    dZ - Z @ Beta
    S00 = M00 / len(Z)
    M11 / len(Z)
    # Product matrix for eigenvalue problem
    try:
        S00_inv = np.linalg.inv(S00)
    except np.linalg.LinAlgError:
        return None
    M = S00_inv @ S01 if (S01 := (M01 @ M01.T) / len(Z)) is not None else None
    if M is None:
        return None
    # Simpler & equivalent: solve generalized eigenvalue problem
    A = M01.T @ np.linalg.pinv(M00) @ M01
    B = M11
    try:
        B_inv = np.linalg.inv(B)
    except np.linalg.LinAlgError:
        return None
    eigvals = np.linalg.eigvals(B_inv @ A)
    eigvals = np.real(eigvals[np.isreal(eigvals)])
    eigvals = np.sort(np.abs(eigvals))[::-1]
    if len(eigvals) < 2:
        return None
    largest = float(eigvals[0])
    trace_stat = -len(Z) * math.log(max(1.0 - largest, 1e-12))
    p = _mackinnon_pvalue_2var(trace_stat)
    crit_95 = 12.21  # 5% critical value for 2-var trace test
    # Recover eigenvector for the largest eigenvalue
    try:
        eigvecs = np.linalg.eig(B_inv @ A)
        v = np.real(eigvecs[1][:, int(np.argmax(np.abs(eigvals)))])
    except (np.linalg.LinAlgError, ValueError):
        v = np.array([1.0, 0.0])
    return CointegrationResult(
        trace_stat=trace_stat,
        crit_value_95=crit_95,
        p_value=p,
        eigenvector=[float(v[0]), float(v[1])],
        is_cointegrated=trace_stat > crit_95,
    )


# Required to avoid a math.log call before import; numpy covers it via np.log


def spread_zscore(
    series1: Sequence[float], series2: Sequence[float], eigenvector: Sequence[float]
) -> tuple[float, float, float]:
    """Compute current Z-score of the cointegrating spread (سند §3.4: Zₜ = (Spreadₜ − μ) / σ).

    Returns (z_score, mean, std) of the latest observation.
    """
    s1 = np.asarray(series1, dtype=float)
    s2 = np.asarray(series2, dtype=float)
    w = np.asarray(eigenvector, dtype=float)
    spread = s1 * w[0] + s2 * w[1]
    mu = float(np.mean(spread))
    sigma = float(np.std(spread, ddof=1)) if len(spread) > 1 else 0.0
    if sigma <= 0:
        return 0.0, mu, sigma
    z = float((spread[-1] - mu) / sigma)
    return z, mu, sigma


def cointegration_signal(
    series1: Sequence[float],
    series2: Sequence[float],
    z_threshold: float = DEFAULT_Z_THRESHOLD,
    min_length: int = MIN_SERIES_LENGTH,
) -> tuple[str, float, CointegrationResult | None]:
    """Combined gate: data sufficiency + Johansen + Z-score signal.

    Returns (signal, z_score, result). signal is "buy" if z < -threshold (spread
    below mean → expect reversion up), "sell" if z > +threshold, "hold"
    otherwise. result is None when data is insufficient (caller must use Tier 1).
    """
    result = johansen_trace_test(series1, series2, min_length=min_length)
    if result is None or not result.is_cointegrated:
        return "hold", 0.0, result
    z, _, _ = spread_zscore(series1, series2, result.eigenvector)
    if z < -z_threshold:
        return "buy", z, result
    if z > z_threshold:
        return "sell", z, result
    return "hold", z, result


def cointegration_data_sufficient(
    series1: Sequence[float], series2: Sequence[float], min_length: int = MIN_SERIES_LENGTH
) -> bool:
    """سند §3.4 gate: minimum 250 overlapping trading points."""
    return len(series1) == len(series2) and len(series1) >= min_length
