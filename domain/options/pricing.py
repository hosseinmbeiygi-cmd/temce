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
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
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

    gamma = npdf_d1 / (S * sigma * math.sqrt(T))
    vega = S * npdf_d1 * math.sqrt(T) / 100.0
    rho = K * T * math.exp(-r * T) * (nd2 if option_type == "call" else -stats.norm.cdf(-d2)) / 100.0

    return OptionPrice(
        model=PRICING_MODEL_BLACK_SCHOLES,
        price=price,
        delta=delta,
        gamma=gamma,
        theta=theta,
        vega=vega,
        rho=rho,
        intrinsic_value=intrinsic,
        time_value=price - intrinsic,
        parameters={"S": S, "K": K, "T": T, "r": r, "sigma": sigma, "option_type": option_type},
    )


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
) -> float:
    """Calculate implied volatility using Newton-Raphson method.
    
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
        Implied volatility
    """
    sigma = initial_guess
    price_fn = black_scholes_call if option_type == "call" else black_scholes_put

    for _ in range(max_iter):
        price = price_fn(S, K, T, r, sigma)
        diff = price - market_price
        if abs(diff) < tol:
            return sigma
        # Vega = dPrice/dSigma
        d1 = _d1(S, K, T, r, sigma)
        vega_val = S * stats.norm.pdf(d1) * math.sqrt(T)
        if abs(vega_val) < 1e-12:
            break
        sigma -= diff / vega_val
        sigma = max(sigma, 1e-6)  # Prevent negative vol

    return sigma
