"""Commodity option pricing with cost of carry (Black-76 / Merton with dividend yield).

Supports:
- Black-Scholes-Merton model with continuous dividend yield q
- Black-76 model for futures-based options
- Implied cost of carry from spot/futures prices
- Physical and cash settlement modes

Market: Iranian commodity options (gold coin, saffron, cumin on IME)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any

from scipy import stats

from domain.options.pricing import PRICING_MODEL_BLACK_SCHOLES, OptionPrice


class SettlementMode(Enum):
    CASH = "cash"
    PHYSICAL = "physical"


class AssetClass(Enum):
    EQUITY = "equity"
    GOLD_COIN = "gold_coin"
    SAFFRON = "saffron"
    CUMIN = "cumin"
    PISTACHIO = "pistachio"


# Contract specifications for Iranian commodity options
CONTRACT_SPECS: dict[AssetClass, dict[str, Any]] = {
    AssetClass.GOLD_COIN: {
        "contract_size": 1,        # 1 gold coin (Bahar Azadi)
        "unit": "coin",
        "settlement": SettlementMode.PHYSICAL,
        "default_carry": 0.28,     # ~28% annual carry (high interest rate environment)
    },
    AssetClass.SAFFRON: {
        "contract_size": 100,      # 100 grams
        "unit": "gram",
        "settlement": SettlementMode.PHYSICAL,
        "default_carry": 0.20,
    },
    AssetClass.CUMIN: {
        "contract_size": 100,      # 100 kg
        "unit": "kg",
        "settlement": SettlementMode.PHYSICAL,
        "default_carry": 0.18,
    },
    AssetClass.PISTACHIO: {
        "contract_size": 100,      # 100 kg
        "unit": "kg",
        "settlement": SettlementMode.PHYSICAL,
        "default_carry": 0.18,
    },
    AssetClass.EQUITY: {
        "contract_size": 1000,     # 1000 shares per contract
        "unit": "share",
        "settlement": SettlementMode.CASH,
        "default_carry": 0.0,
    },
}


@dataclass
class CommodityOptionParams:
    """Parameters for commodity option pricing."""
    S: float                    # Current spot price
    K: float                    # Strike price
    T: float                    # Time to expiry (years)
    r: float                    # Risk-free rate (Iranian interbank ~23-30%)
    q: float = 0.0              # Continuous dividend yield / cost of carry
    sigma: float = 0.30         # Implied volatility
    option_type: str = "call"   # "call" or "put"
    asset_class: AssetClass = AssetClass.EQUITY
    settlement: SettlementMode = SettlementMode.CASH
    futures_price: float | None = None  # For Black-76 model


def implied_cost_of_carry(spot_price: float, futures_price: float, T: float) -> float:
    """Calculate implied cost of carry from spot and futures prices.

    F = S * exp(b * T)  =>  b = ln(F/S) / T

    For Iranian gold coin: high interest rates make b ≈ r (25-30%)
    """
    if T <= 0 or spot_price <= 0 or futures_price <= 0:
        return 0.0
    return math.log(futures_price / spot_price) / T


def commodity_bs_d1(d1_val: float) -> float:
    return d1_val


def commodity_bs_call(S: float, K: float, T: float, r: float, q: float, sigma: float) -> float:
    """Black-Scholes call with continuous dividend yield q.

    C = S * exp(-q*T) * N(d1) - K * exp(-r*T) * N(d2)

    where:
        d1 = [ln(S/K) + (r - q + sigma^2/2) * T] / (sigma * sqrt(T))
        d2 = d1 - sigma * sqrt(T)
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return max(0.0, S - K)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return float(S * math.exp(-q * T) * stats.norm.cdf(d1) - K * math.exp(-r * T) * stats.norm.cdf(d2))


def commodity_bs_put(S: float, K: float, T: float, r: float, q: float, sigma: float) -> float:
    """Black-Scholes put with continuous dividend yield q."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return max(0.0, K - S)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return float(K * math.exp(-r * T) * stats.norm.cdf(-d2) - S * math.exp(-q * T) * stats.norm.cdf(-d1))


def black76_call(F: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-76 model for futures options.

    C = exp(-r*T) * [F * N(d1) - K * N(d2)]

    Used for commodity options where underlying is a futures contract.
    """
    if T <= 0 or sigma <= 0 or F <= 0 or K <= 0:
        return max(0.0, F - K)
    d1 = (math.log(F / K) + 0.5 * sigma**2 * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return float(math.exp(-r * T) * (F * stats.norm.cdf(d1) - K * stats.norm.cdf(d2)))


def black76_put(F: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-76 model for futures options."""
    if T <= 0 or sigma <= 0 or F <= 0 or K <= 0:
        return max(0.0, K - F)
    d1 = (math.log(F / K) + 0.5 * sigma**2 * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return float(math.exp(-r * T) * (K * stats.norm.cdf(-d2) - F * stats.norm.cdf(-d1)))


def price_commodity_option(params: CommodityOptionParams) -> OptionPrice:
    """Full pricing with Greeks for commodity options.

    Automatically selects Black-Scholes-Merton (with q) or Black-76 (with futures_price).
    Returns OptionPrice with price, Greeks, and metadata.
    """
    S, K, T, r, q, sigma = params.S, params.K, params.T, params.r, params.q, params.sigma

    if T <= 0 or sigma <= 0:
        intrinsic = max(0.0, S - K) if params.option_type == "call" else max(0.0, K - S)
        return OptionPrice(
            model=PRICING_MODEL_BLACK_SCHOLES,
            price=intrinsic,
            intrinsic_value=intrinsic,
            parameters={"model": "commodity_bs", "q": q, "asset_class": params.asset_class.value},
        )

    # Choose model
    if params.futures_price is not None:
        # Black-76 model
        price_fn = black76_call if params.option_type == "call" else black76_put
        price = price_fn(params.futures_price, K, T, r, sigma)
        F = params.futures_price
        d1 = (math.log(F / K) + 0.5 * sigma**2 * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        exp_rt = math.exp(-r * T)
        pdf_d1 = stats.norm.pdf(d1)
        if params.option_type == "call":
            delta = exp_rt * stats.norm.cdf(d1)
            theta_annual = (exp_rt * (-F * pdf_d1 * sigma / (2 * math.sqrt(T)))
                           - r * F * exp_rt * stats.norm.cdf(d1)
                           + r * K * exp_rt * stats.norm.cdf(d2))
        else:
            delta = -exp_rt * stats.norm.cdf(-d1)
            theta_annual = (exp_rt * (F * pdf_d1 * sigma / (2 * math.sqrt(T)))
                           + r * F * exp_rt * stats.norm.cdf(-d1)
                           - r * K * exp_rt * stats.norm.cdf(-d2))
    else:
        # Black-Scholes-Merton with dividend yield q
        price_fn = commodity_bs_call if params.option_type == "call" else commodity_bs_put  # type: ignore[assignment]
        price = price_fn(S, K, T, r, q, sigma)  # type: ignore[call-arg]

        d1 = (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        pdf_d1 = stats.norm.pdf(d1)
        nd1 = stats.norm.cdf(d1)
        eqT = math.exp(-q * T)
        erT = math.exp(-r * T)

        if params.option_type == "call":
            delta = eqT * nd1
            theta_annual = (-S * eqT * pdf_d1 * sigma / (2 * math.sqrt(T))
                           - q * S * eqT * nd1
                           + r * K * erT * stats.norm.cdf(d2))
        else:
            delta = -eqT * stats.norm.cdf(-d1)
            theta_annual = (-S * eqT * pdf_d1 * sigma / (2 * math.sqrt(T))
                           + q * S * eqT * stats.norm.cdf(-d1)
                           - r * K * erT * stats.norm.cdf(-d2))

    gamma = (pdf_d1 / (S * sigma * math.sqrt(T))) if params.futures_price is None else (
        exp_rt * pdf_d1 / (F * sigma * math.sqrt(T))
    )
    vega = S * pdf_d1 * math.sqrt(T) / 100.0 if params.futures_price is None else (
        exp_rt * F * pdf_d1 * math.sqrt(T) / 100.0
    )
    rho = (K * T * erT * (stats.norm.cdf(d2) if params.option_type == "call" else -stats.norm.cdf(-d2))) / 100.0

    intrinsic = max(0.0, S - K) if params.option_type == "call" else max(0.0, K - S)

    return OptionPrice(
        model=PRICING_MODEL_BLACK_SCHOLES,
        price=price,
        delta=delta,
        gamma=gamma,
        theta=theta_annual / 365.0,
        vega=vega,
        rho=rho,
        intrinsic_value=intrinsic,
        time_value=price - intrinsic,
        parameters={
            "model": "commodity_bs",
            "q": q,
            "asset_class": params.asset_class.value,
            "settlement": params.settlement.value,
            "futures_price": params.futures_price,
            "S": S, "K": K, "T": T, "r": r, "sigma": sigma,
        },
    )


def implied_volatility_commodity(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    q: float = 0.0,
    option_type: str = "call",
    initial_guess: float = 0.3,
    max_iter: int = 100,
    tol: float = 1e-6,
) -> float:
    """Newton-Raphson implied volatility for commodity options with q."""
    sigma = initial_guess
    price_fn = commodity_bs_call if option_type == "call" else commodity_bs_put

    for _ in range(max_iter):
        price = price_fn(S, K, T, r, q, sigma)
        diff = price - market_price
        if abs(diff) < tol:
            return float(sigma)
        d1 = (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        vega_val = S * math.exp(-q * T) * stats.norm.pdf(d1) * math.sqrt(T)
        if abs(vega_val) < 1e-12:
            break
        sigma -= diff / float(vega_val)
        sigma = max(sigma, 1e-6)

    return float(sigma)
