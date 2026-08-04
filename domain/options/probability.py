"""Probability of Touch (POT) calculator.

Calculates the probability that the underlying price will reach a specific
level (strike or target) before expiry. Useful for:
- Setting stop-loss and take-profit levels
- Evaluating short option risk
- Determining whether an ITM option will be exercised

Uses:
- Barone-Adesi & Whaley approximation
- Monte Carlo simulation
- Analytic formula for Brownian motion with drift
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats


def probability_of_touch_brownian(
    S: float,
    target: float,
    T: float,
    r: float,
    sigma: float,
    q: float = 0.0,
) -> float:
    """Probability that price hits target before expiry using Brownian motion.

    For a GBM with drift μ = r - q - σ²/2:
    P(hit target) = N(d+) + (target/S)^(2μ/σ²) * N(d-)

    where:
    d+ = [ln(target/S) + μ*T] / (σ*sqrt(T))
    d- = [ln(target/S) - μ*T] / (σ*sqrt(T))
    """
    if T <= 0 or sigma <= 0 or S <= 0 or target <= 0:
        return 0.0

    mu = r - q - 0.5 * sigma**2
    sigma_sqrt_T = sigma * math.sqrt(T)

    if abs(target - S) < 1e-10:
        return 1.0

    ln_ratio = math.log(target / S)

    d_plus = (ln_ratio + mu * T) / sigma_sqrt_T
    d_minus = (ln_ratio - mu * T) / sigma_sqrt_T

    exponent = 2 * mu * ln_ratio / (sigma**2)

    prob = stats.norm.cdf(d_plus) + (target / S) ** exponent * stats.norm.cdf(-d_minus)

    return float(min(max(prob, 0.0), 1.0))


def probability_of_touch_monte_carlo(
    S: float,
    target: float,
    T: float,
    r: float,
    sigma: float,
    q: float = 0.0,
    n_paths: int = 50000,
    n_steps: int = 252,
    seed: int = 42,
) -> float:
    """Monte Carlo simulation for probability of touch.

    More accurate for complex scenarios (barriers, partial barriers).
    """
    if T <= 0 or sigma <= 0 or S <= 0 or target <= 0:
        return 0.0

    rng = np.random.default_rng(seed)
    dt = T / n_steps

    # Simulate paths
    Z = rng.standard_normal((n_paths, n_steps))
    drift = (r - q - 0.5 * sigma**2) * dt
    diffusion = sigma * np.sqrt(dt)

    log_returns = drift + diffusion * Z
    log_price_paths = np.cumsum(log_returns, axis=1)
    price_paths = S * np.exp(log_price_paths)

    # Prepend initial price
    initial_col = np.full((n_paths, 1), S)
    price_paths = np.hstack([initial_col, price_paths])

    # Check if any path touched the target
    touched = np.any(price_paths >= target, axis=1) if target > S else np.any(price_paths <= target, axis=1)

    return float(np.mean(touched))


def probability_itm_at_expiry(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float = 0.0,
    option_type: str = "call",
) -> float:
    """Probability that option expires in-the-money.

    For call: P(S_T > K) = N(d2)
    For put: P(S_T < K) = N(-d2)
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        if option_type == "call":
            return 1.0 if S > K else 0.0
        else:
            return 1.0 if K > S else 0.0

    d1 = (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    if option_type == "call":
        return float(stats.norm.cdf(d2))
    else:
        return float(stats.norm.cdf(-d2))


def probability_otm_at_expiry(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float = 0.0,
    option_type: str = "call",
) -> float:
    """Probability that option expires out-of-the-money (worthless)."""
    return 1.0 - probability_itm_at_expiry(S, K, T, r, sigma, q, option_type)


def expected_move(
    S: float,
    sigma: float,
    T: float,
    confidence: float = 0.68,
) -> tuple[float, float]:
    """Expected price range (move) for the underlying.

    Returns (lower_bound, upper_bound) based on implied volatility.
    Default 68% confidence (1 standard deviation).
    """
    z = stats.norm.ppf((1 + confidence) / 2)
    move = S * sigma * math.sqrt(T) * z
    return S - move, S + move


def max_pain_price(strikes: list[float], open_interests: list[float]) -> float:
    """Calculate the max pain price for an options chain.

    Max pain is the strike price at which the total payout to option holders
    is minimized (maximum pain for buyers).
    """
    if not strikes or not open_interests:
        return 0.0

    min_pain = float("inf")
    max_pain_strike = strikes[0]

    for test_strike in strikes:
        total_pain = 0.0
        for strike, oi in zip(strikes, open_interests, strict=False):
            if test_strike > strike:
                total_pain += (test_strike - strike) * oi
            elif test_strike < strike:
                total_pain += (strike - test_strike) * oi

        if total_pain < min_pain:
            min_pain = total_pain
            max_pain_strike = test_strike

    return max_pain_strike
