from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from scipy import stats

PRICING_MODEL_BLACK_SCHOLES = "black_scholes"
PRICING_MODEL_BINOMIAL = "binomial"
PRICING_MODEL_MONTE_CARLO = "monte_carlo"
PRICING_MODEL_WHITE = "whale"


@dataclass
class OptionPrice:
    model: str = ""
    price: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    implied_vol: float = 0.0
    intrinsic_value: float = 0.0
    time_value: float = 0.0
    parameters: dict[str, Any] = field(default_factory=dict)


def _d1(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Calculate d1 in Black-Scholes formula.

    d1 = (ln(S/K) + (r + sigma^2/2) * T) / (sigma * sqrt(T))
    """
    return (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))


def _vol_sqrt_t(sigma: float, T: float) -> float:
    """``sigma * sqrt(T)``, the Black-Scholes time-vol scale.

    Returns 0.0 when the product underflows to zero. Guarding only
    ``T <= 0 or sigma <= 0`` misses ``sigma=1e-300, T=1e-300``, where the
    product is exactly 0.0 and ``_d1`` raises ZeroDivisionError.
    """
    try:
        value = sigma * math.sqrt(T)
    except (OverflowError, ValueError):
        return 0.0
    return value if math.isfinite(value) else 0.0


def _d2(d1: float, sigma: float, T: float) -> float:
    """Calculate d2 in Black-Scholes formula.

    d2 = d1 - sigma * sqrt(T)
    """
    return d1 - sigma * math.sqrt(T)


def black_scholes_call(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes call option price.

    Args:
        S: Current asset price
        K: Strike price
        T: Time to expiration (in years)
        r: Risk-free interest rate (decimal)
        sigma: Volatility (decimal)

    Returns:
        Call option price
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return max(0.0, S - K)
    if _vol_sqrt_t(sigma, T) <= 0.0:
        return max(0.0, S - K)
    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(d1, sigma, T)
    return S * stats.norm.cdf(d1) - K * math.exp(-r * T) * stats.norm.cdf(d2)


def black_scholes_put(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes put option price.

    Args:
        S: Current asset price
        K: Strike price
        T: Time to expiration (in years)
        r: Risk-free interest rate (decimal)
        sigma: Volatility (decimal)

    Returns:
        Put option price
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return max(0.0, K - S)
    if _vol_sqrt_t(sigma, T) <= 0.0:
        return max(0.0, K - S)
    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(d1, sigma, T)
    return K * math.exp(-r * T) * stats.norm.cdf(-d2) - S * stats.norm.cdf(-d1)


def black_scholes_price(S: float, K: float, T: float, r: float, sigma: float, option_type: str = "call") -> OptionPrice:
    """Full Black-Scholes pricing with all Greeks.

    Args:
        S: Current asset price
        K: Strike price
        T: Time to expiration (in years)
        r: Risk-free interest rate (decimal, e.g. 0.05 for 5%%)
        sigma: Volatility (decimal, e.g. 0.30 for 30%%)
        option_type: "call" or "put"

    Returns:
        OptionPrice dataclass with price, Greeks, and intrinsic/time values.
        Theta is per calendar day. Vega is per 1%% vol change. Rho is per 1%% rate change.
    """
    degenerate = T <= 0 or sigma <= 0 or S <= 0 or K <= 0
    if not degenerate:
        degenerate = _vol_sqrt_t(sigma, T) <= 0.0
    if degenerate:
        intrinsic = max(0.0, S - K) if option_type == "call" else max(0.0, K - S)
        return OptionPrice(
            model=PRICING_MODEL_BLACK_SCHOLES,
            price=intrinsic,
            intrinsic_value=intrinsic,
            time_value=0.0,
            parameters={"S": S, "K": K, "T": T, "r": r, "sigma": sigma, "option_type": option_type},
        )

    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(d1, sigma, T)
    nd1 = stats.norm.cdf(d1)
    nd2 = stats.norm.cdf(d2)
    npdf_d1 = stats.norm.pdf(d1)

    if option_type == "call":
        price = S * nd1 - K * math.exp(-r * T) * nd2
        delta = nd1
        theta = (-S * npdf_d1 * sigma / (2 * math.sqrt(T))
                 - r * K * math.exp(-r * T) * nd2) / 365.0
        intrinsic = max(0.0, S - K)
    else:
        price = K * math.exp(-r * T) * stats.norm.cdf(-d2) - S * stats.norm.cdf(-d1)
        delta = nd1 - 1
        theta = (-S * npdf_d1 * sigma / (2 * math.sqrt(T))
                 + r * K * math.exp(-r * T) * stats.norm.cdf(-d2)) / 365.0
        intrinsic = max(0.0, K - S)

    # Guard against near-zero sigma*sqrt(T) that would produce inf gamma
    denom = S * sigma * math.sqrt(T)
    if denom < 1e-12 or not math.isfinite(denom):
        gamma = 0.0
    else:
        gamma = npdf_d1 / denom
        if not math.isfinite(gamma):
            gamma = 0.0
    vega = S * npdf_d1 * math.sqrt(T) / 100.0
    if not math.isfinite(vega):
        vega = 0.0
    rho = K * T * math.exp(-r * T) * (nd2 if option_type == "call" else -stats.norm.cdf(-d2)) / 100.0
    if not math.isfinite(rho):
        rho = 0.0

    # API contract: every number here is serialised with allow_nan=False, so a
    # single inf/NaN must never escape (extreme sigma/T can overflow theta).
    if not math.isfinite(price):
        price = intrinsic
    if not math.isfinite(delta):
        delta = 0.0
    if not math.isfinite(theta):
        theta = 0.0
    time_value = price - intrinsic
    if not math.isfinite(time_value):
        time_value = 0.0

    return OptionPrice(
        model=PRICING_MODEL_BLACK_SCHOLES,
        price=price,
        delta=delta,
        gamma=gamma,
        theta=theta,
        vega=vega,
        rho=rho,
        intrinsic_value=intrinsic,
        time_value=time_value,
        parameters={"S": S, "K": K, "T": T, "r": r, "sigma": sigma, "option_type": option_type},
    )


IV_MIN = 1e-4
IV_MAX = 5.0


def implied_volatility(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: str = "call",
    initial_guess: float = 0.3,
    max_iter: int = 100,
    tol: float = 1e-6,
) -> float | None:
    """Calculate implied volatility with a bracketed fallback.

    Returns ``None`` when the quote is outside the no-arbitrage band or the
    solver does not converge (audit FIN-04). The old ``0.0`` sentinel for
    expiry and the unverified last iterate were displayed as valid IV by the
    options analytics surface.

    Args:
        market_price: Observed market price of the option
        S: Current asset price
        K: Strike price
        T: Time to expiration (in years)
        r: Risk-free interest rate
        option_type: "call" or "put"
        initial_guess: Starting volatility estimate
        max_iter: Maximum iterations
        tol: Convergence tolerance

    Returns:
        Implied volatility in ``[IV_MIN, IV_MAX]``, or ``None``.
    """
    values = (market_price, S, K, T, r)
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values):
        return None
    if T <= 0 or S <= 0 or K <= 0 or market_price <= 0:
        return None

    discount = math.exp(-r * T)
    if option_type == "call":
        lower_bound = max(S - K * discount, 0.0)
        upper_bound = S
    else:
        lower_bound = max(K * discount - S, 0.0)
        upper_bound = K * discount
    if market_price < lower_bound - 1e-9 or market_price > upper_bound + 1e-9:
        # Below intrinsic or above the theoretical maximum: no real sigma.
        return None

    price_fn = black_scholes_call if option_type == "call" else black_scholes_put

    def residual(sigma: float) -> float:
        return price_fn(S, K, T, r, sigma) - market_price

    sigma = min(max(initial_guess, IV_MIN), IV_MAX)
    for _ in range(max_iter):
        diff = residual(sigma)
        if abs(diff) < tol:
            return sigma
        d1 = _d1(S, K, T, r, sigma)
        vega_val = S * stats.norm.pdf(d1) * math.sqrt(T)
        if abs(vega_val) < 1e-12:
            break
        sigma -= diff / vega_val
        if not math.isfinite(sigma) or sigma <= IV_MIN or sigma >= IV_MAX:
            break

    # Bracketed bisection: guaranteed when a root exists inside the band.
    lo, hi = IV_MIN, IV_MAX
    f_lo, f_hi = residual(lo), residual(hi)
    if f_lo * f_hi > 0:
        return None
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        f_mid = residual(mid)
        if abs(f_mid) < tol:
            return mid
        if (f_lo < 0) == (f_mid < 0):
            lo, f_lo = mid, f_mid
        else:
            hi = mid
    return None

