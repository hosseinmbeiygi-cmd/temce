"""General Monte Carlo option pricing (European + American/Bermudan via LSM).

سند v5.0 §3.1: مدل Tier 1 Black-76 پیش‌فرض؛ Tier 2 اختیاری و مشروط به کفایت
داده. این ماژول پایه MC را برای آپشن‌های European (BS baseline) و American/
Bermudan (Longstaff-Schwartz) فراهم می‌کند تا سایر لایه‌ها (Hard Block §4.3،
Walk-Forward §7.1) بتوانند به‌جای فرض نقطه‌ای، توزیع لغزش/قیمت تولید کنند.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.stats import norm

# ── European (GBSM with continuous carry q) ──────────────────────────────────


@dataclass
class MCResult:
    price: float
    std_error: float
    ci_low: float
    ci_high: float
    n_paths: int
    n_steps: int
    model: str = "european_mc"


def _european_payoff(S_terminal: np.ndarray, K: float, option_type: str) -> np.ndarray:
    if option_type == "call":
        return np.maximum(S_terminal - K, 0.0)
    return np.maximum(K - S_terminal, 0.0)


def monte_carlo_european(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float = 0.0,
    n_paths: int = 10_000,
    n_steps: int = 252,
    seed: int = 42,
    option_type: str = "call",
    antithetic: bool = True,
) -> MCResult:
    """Geometric-Brownian-motion Monte Carlo under the risk-neutral measure.

    Returns price, std error, and 95% CI. With antithetic variates (default),
    n_paths is halved to use Z and -Z pair — halves variance for smooth payoffs.
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        intrinsic = max(0.0, S - K) if option_type == "call" else max(0.0, K - S)
        return MCResult(price=intrinsic, std_error=0.0, ci_low=intrinsic, ci_high=intrinsic, n_paths=0, n_steps=n_steps)

    rng = np.random.default_rng(seed)
    actual_paths = n_paths // 2 if antithetic else n_paths
    dt = T / n_steps
    drift = (r - q - 0.5 * sigma**2) * dt
    diffusion = sigma * math.sqrt(dt)

    Z = rng.standard_normal(size=(n_steps, actual_paths))
    if antithetic:
        Z = np.concatenate([Z, -Z], axis=1)

    log_increments = drift + diffusion * Z
    log_S = math.log(S) + np.cumsum(log_increments, axis=0)
    S_terminal = np.exp(log_S[-1])
    payoffs = _european_payoff(S_terminal, K, option_type)
    discount = math.exp(-r * T)
    discounted = discount * payoffs
    price = float(np.mean(discounted))
    std_error = float(np.std(discounted, ddof=1) / math.sqrt(discounted.size))
    ci_low = price - 1.96 * std_error
    ci_high = price + 1.96 * std_error
    return MCResult(
        price=price, std_error=std_error, ci_low=ci_low, ci_high=ci_high, n_paths=discounted.size, n_steps=n_steps
    )


# ── American / Bermudan (Longstaff-Schwartz, regression on polynomial basis) ─


def _longstaff_swartz_basis(S: np.ndarray) -> np.ndarray:
    """Degree-3 polynomial basis (1, S, S², S³) — sufficient for vanilla payoffs."""
    return np.column_stack([np.ones_like(S), S, S**2, S**3])


def monte_carlo_american_lsm(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float = 0.0,
    n_paths: int = 10_000,
    n_steps: int = 50,
    seed: int = 42,
    option_type: str = "put",
    antithetic: bool = True,
) -> MCResult:
    """Longstaff-Schwartz least-squares Monte Carlo for American/Bermudan vanilla.

    Uses polynomial regression of continuation value on the underlying. Sends
    the optimal stopping decision backward through the time grid, then averages
    the discounted cash-flows across paths.
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        intrinsic = max(0.0, S - K) if option_type == "call" else max(0.0, K - S)
        return MCResult(
            price=intrinsic,
            std_error=0.0,
            ci_low=intrinsic,
            ci_high=intrinsic,
            n_paths=0,
            n_steps=n_steps,
            model="american_lsm",
        )

    rng = np.random.default_rng(seed)
    actual_paths = n_paths // 2 if antithetic else n_paths
    dt = T / n_steps
    drift = (r - q - 0.5 * sigma**2) * dt
    diffusion = sigma * math.sqrt(dt)
    discount_step = math.exp(-r * dt)

    Z = rng.standard_normal(size=(n_steps, actual_paths))
    if antithetic:
        Z = np.concatenate([Z, -Z], axis=1)

    log_increments = drift + diffusion * Z
    log_S = math.log(S) + np.cumsum(log_increments, axis=0)
    paths = np.exp(log_S)
    # Insert initial S at time 0
    paths = np.vstack([np.full((1, paths.shape[1]), S), paths])  # shape (n_steps+1, n_paths)

    intrinsic = (lambda s: np.maximum(s - K, 0.0)) if option_type == "call" else lambda s: np.maximum(K - s, 0.0)

    cashflow = intrinsic(paths[-1])
    exercise_time = np.full(paths.shape[1], n_steps, dtype=int)
    # Backward induction
    for t in range(n_steps - 1, 0, -1):
        intrinsic_now = intrinsic(paths[t])
        itm = intrinsic_now > 0
        if not itm.any():
            cashflow = discount_step * cashflow
            continue
        # Discount future cashflows to t
        future = cashflow * (discount_step ** (exercise_time - t))
        X = paths[t, itm]
        Y = future[itm]
        basis = _longstaff_swartz_basis(X)
        # Stable fit: least squares
        coeffs, *_ = np.linalg.lstsq(basis, Y, rcond=None)
        continuation = basis @ coeffs
        exercise_now = intrinsic_now[itm] >= continuation
        idx = np.where(itm)[0][exercise_now]
        cashflow[idx] = intrinsic_now[idx]
        exercise_time[idx] = t
        # Update non-exercised paths: discount by one step
        non_ex = np.setdiff1d(np.arange(paths.shape[1]), idx, assume_unique=False)
        cashflow[non_ex] = discount_step * cashflow[non_ex]

    # Final discount to t=0 for cashflows exercised at time > 0
    price_paths = cashflow * (discount_step**exercise_time)
    price = float(np.mean(price_paths))
    std_error = float(np.std(price_paths, ddof=1) / math.sqrt(price_paths.size))
    return MCResult(
        price=price,
        std_error=std_error,
        ci_low=price - 1.96 * std_error,
        ci_high=price + 1.96 * std_error,
        n_paths=price_paths.size,
        n_steps=n_steps,
        model="american_lsm",
    )


# ── Sanity helpers (analytical for European; used as regression test) ────────


def black_scholes_european(
    S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0, option_type: str = "call"
) -> float:
    """BSM with continuous carry — for tests only; the canonical pricing engine
    remains domain.options.pricing.black_scholes_price.
    """
    if T <= 0 or sigma <= 0:
        return max(0.0, S - K) if option_type == "call" else max(0.0, K - S)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if option_type == "call":
        return float(S * math.exp(-q * T) * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2))
    return float(K * math.exp(-r * T) * norm.cdf(-d2) - S * math.exp(-q * T) * norm.cdf(-d1))
