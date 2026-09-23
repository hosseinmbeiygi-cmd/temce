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
from scipy.optimize import brentq

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
        "contract_size": 1,  # 1 gold coin (Bahar Azadi)
        "unit": "coin",
        "settlement": SettlementMode.PHYSICAL,
        "default_carry": 0.28,  # ~28% annual carry (high interest rate environment)
    },
    AssetClass.SAFFRON: {
        "contract_size": 100,  # 100 grams
        "unit": "gram",
        "settlement": SettlementMode.PHYSICAL,
        "default_carry": 0.20,
    },
    AssetClass.CUMIN: {
        "contract_size": 100,  # 100 kg
        "unit": "kg",
        "settlement": SettlementMode.PHYSICAL,
        "default_carry": 0.18,
    },
    AssetClass.PISTACHIO: {
        "contract_size": 100,  # 100 kg
        "unit": "kg",
        "settlement": SettlementMode.PHYSICAL,
        "default_carry": 0.18,
    },
    AssetClass.EQUITY: {
        "contract_size": 1000,  # 1000 shares per contract
        "unit": "share",
        "settlement": SettlementMode.CASH,
        "default_carry": 0.0,
    },
}


@dataclass
class CommodityOptionParams:
    """Parameters for commodity option pricing."""

    S: float  # Current spot price
    K: float  # Strike price
    T: float  # Time to expiry (years)
    r: float  # Risk-free rate (Iranian interbank ~23-30%)
    q: float = 0.0  # Continuous dividend yield / cost of carry
    sigma: float = 0.30  # Implied volatility
    option_type: str = "call"  # "call" or "put"
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

    # Guard invalid / degenerate inputs before any log()/sqrt() so Greeks never hit
    # inf/nan and JSON serializers downstream stay healthy.
    if params.futures_price is not None:
        # Black-76 path: underlying is a futures price.
        if T <= 0 or sigma <= 0 or params.futures_price <= 0 or K <= 0:
            return OptionPrice(
                model=PRICING_MODEL_BLACK_SCHOLES,
                price=0.0,
                intrinsic_value=0.0,
                parameters={
                    "model": "commodity_bs",
                    "error": "invalid_inputs",
                    "asset_class": params.asset_class.value,
                    "futures_price": params.futures_price,
                    "S": S,
                    "K": K,
                    "T": T,
                    "r": r,
                    "sigma": sigma,
                },
            )
    else:
        # Black-Scholes-Merton with dividend yield q.
        if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
            return OptionPrice(
                model=PRICING_MODEL_BLACK_SCHOLES,
                price=0.0,
                intrinsic_value=0.0,
                parameters={
                    "model": "commodity_bs",
                    "error": "invalid_inputs",
                    "asset_class": params.asset_class.value,
                    "futures_price": params.futures_price,
                    "S": S,
                    "K": K,
                    "T": T,
                    "r": r,
                    "sigma": sigma,
                },
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
            theta_annual = (
                exp_rt * (-F * pdf_d1 * sigma / (2 * math.sqrt(T)))
                - r * F * exp_rt * stats.norm.cdf(d1)
                + r * K * exp_rt * stats.norm.cdf(d2)
            )
        else:
            delta = -exp_rt * stats.norm.cdf(-d1)
            theta_annual = (
                exp_rt * (F * pdf_d1 * sigma / (2 * math.sqrt(T)))
                + r * F * exp_rt * stats.norm.cdf(-d1)
                - r * K * exp_rt * stats.norm.cdf(-d2)
            )
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
            theta_annual = (
                -S * eqT * pdf_d1 * sigma / (2 * math.sqrt(T)) - q * S * eqT * nd1 + r * K * erT * stats.norm.cdf(d2)
            )
        else:
            delta = -eqT * stats.norm.cdf(-d1)
            theta_annual = (
                -S * eqT * pdf_d1 * sigma / (2 * math.sqrt(T))
                + q * S * eqT * stats.norm.cdf(-d1)
                - r * K * erT * stats.norm.cdf(-d2)
            )

    _gden = (S * sigma * math.sqrt(T)) if params.futures_price is None else (F * sigma * math.sqrt(T))
    if not math.isfinite(_gden) or _gden < 1e-12:
        gamma = 0.0
    else:
        gamma = (
            (pdf_d1 / _gden)
            if params.futures_price is None
            else (exp_rt * pdf_d1 / _gden)
        )
        if not math.isfinite(gamma):
            gamma = 0.0
    vega = (
        S * pdf_d1 * math.sqrt(T) / 100.0
        if params.futures_price is None
        else (exp_rt * F * pdf_d1 * math.sqrt(T) / 100.0)
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
            "S": S,
            "K": K,
            "T": T,
            "r": r,
            "sigma": sigma,
        },
    )


def implied_vol_commodity_option(
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
    # Guard degenerate / invalid inputs: Newton-Raphson would divide by zero
    # (sigma*sqrt(T) in d1) or walk off to inf/nan.
    if S <= 0 or K <= 0 or T <= 0 or initial_guess <= 0:
        return float(initial_guess)

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


# =============================================================================
# Tier 1/2 pricing per IME v5.0 architecture doc (§3.1–§3.4)
# =============================================================================


def displaced_diffusion_call(F: float, K: float, T: float, r: float, sigma: float, alpha: float) -> float:
    """Displaced Diffusion call on a futures (Tier 2, conditional on verified α floor).

    C = e^(−rT) · [(F+α)·N(d₁) − (K+α)·N(d₂)]
    d₁ = [ln((F+α)/(K+α)) + ½σ²T] / (σ√T)

    Reduces to Black-76 exactly when α = 0. α (price floor from official source)
    must satisfy the verification gate before use — see `displaced_diffusion_allowed`.
    """
    if T <= 0 or sigma <= 0 or (F + alpha) <= 0 or (K + alpha) <= 0:
        return max(0.0, F - K)
    if alpha == 0.0:
        return black76_call(F, K, T, r, sigma)
    Fs, Ks = F + alpha, K + alpha
    d1 = (math.log(Fs / Ks) + 0.5 * sigma**2 * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return float(math.exp(-r * T) * (Fs * stats.norm.cdf(d1) - Ks * stats.norm.cdf(d2)))


def displaced_diffusion_put(F: float, K: float, T: float, r: float, sigma: float, alpha: float) -> float:
    """Displaced Diffusion put on a futures (Tier 2). Reduces to Black-76 at α = 0."""
    if T <= 0 or sigma <= 0 or (F + alpha) <= 0 or (K + alpha) <= 0:
        return max(0.0, K - F)
    if alpha == 0.0:
        return black76_put(F, K, T, r, sigma)
    Fs, Ks = F + alpha, K + alpha
    d1 = (math.log(Fs / Ks) + 0.5 * sigma**2 * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return float(math.exp(-r * T) * (Ks * stats.norm.cdf(-d2) - Fs * stats.norm.cdf(-d1)))


def alpha_floor_verified(alpha: float, source: str | None, has_timestamp: bool) -> bool:
    """Tier-2 gate: α must come from an official source with a valid timestamp.

    سند §3.1: ورود دستی α بدون منبع رسمی و بدون Timestamp معتبر ممنوع است —
    چون خودش منبع خطای سیستماتیک می‌شود.
    """
    return alpha >= 0.0 and bool(source) and has_timestamp


def displaced_diffusion_allowed(alpha: float, source: str | None, has_timestamp: bool) -> bool:
    """Full Tier-2 precondition: verified α floor AND valid model inputs."""
    return alpha_floor_verified(alpha, source, has_timestamp)


def price_displaced_diffusion(
    F: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    alpha: float,
    option_type: str = "call",
    model_version: str = "ime-v5.0-dd-1",
) -> OptionPrice | None:
    """Price with closed-form Greeks; None when the Tier-2 precondition fails.

    Greeks follow the displaced forms: delta = e^(−rT)·N(d₁),
    gamma = e^(−rT)·φ(d₁)/((F+α)·σ√T), vega = e^(−rT)·(F+α)·φ(d₁)·√T/100.
    """
    if alpha > 0 and not displaced_diffusion_allowed(alpha, source=None, has_timestamp=False):
        return None
    if T <= 0 or sigma <= 0 or F <= 0 or K <= 0:
        intrinsic = max(0.0, F - K) if option_type == "call" else max(0.0, K - F)
        return OptionPrice(
            model="ime_displaced_diffusion",
            price=intrinsic,
            intrinsic_value=intrinsic,
            parameters={"model_version": model_version},
        )

    Fs, Ks = F + alpha, K + alpha
    d1 = (math.log(Fs / Ks) + 0.5 * sigma**2 * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    erT = math.exp(-r * T)
    pdf = stats.norm.pdf(d1)
    nd1, nd2 = stats.norm.cdf(d1), stats.norm.cdf(d2)

    if option_type == "call":
        price = erT * (Fs * nd1 - Ks * nd2)
        delta = erT * nd1
        theta_annual = erT * (-Fs * pdf * sigma / (2 * math.sqrt(T)) - r * Fs * nd1 + r * Ks * nd2)
    else:
        price = erT * (Ks * stats.norm.cdf(-d2) - Fs * stats.norm.cdf(-d1))
        delta = -erT * stats.norm.cdf(-d1)
        theta_annual = erT * (
            Fs * pdf * sigma / (2 * math.sqrt(T)) + r * Fs * stats.norm.cdf(-d1) - r * Ks * stats.norm.cdf(-d2)
        )

    denom = Fs * sigma * math.sqrt(T)
    gamma = erT * pdf / denom if denom > 1e-12 else 0.0
    vega = erT * Fs * pdf * math.sqrt(T) / 100.0
    rho = (Ks * T * erT * (nd2 if option_type == "call" else -stats.norm.cdf(-d2))) / 100.0

    intrinsic = max(0.0, F - K) if option_type == "call" else max(0.0, K - F)
    return OptionPrice(
        model="ime_displaced_diffusion",
        price=price,
        delta=delta,
        gamma=gamma,
        theta=theta_annual / 365.0,
        vega=vega,
        rho=rho,
        implied_vol=sigma,
        intrinsic_value=intrinsic,
        time_value=price - intrinsic,
        parameters={
            "model": "displaced_diffusion",
            "alpha": alpha,
            "F": F,
            "K": K,
            "T": T,
            "r": r,
            "sigma": sigma,
            "option_type": option_type,
            "model_version": model_version,
        },
    )


def put_call_parity_violation(
    call_price: float, put_price: float, F: float, K: float, T: float, r: float, tol: float = 1e-6
) -> bool:
    """True when a call/put pair violates futures put-call parity.

    C − P = e^(−rT)·(F − K)   ⇒   violation if |C − P − e^(−rT)(F − K)| > tol.
    سند §3.2: قیمت‌های ناقض Put-Call Parity پیش از محاسبه IV حذف می‌شوند.
    """
    if T <= 0 or F <= 0 or K <= 0:
        return False
    parity = math.exp(-r * T) * (F - K)
    return abs(call_price - put_price - parity) > tol


def _solve_implied_vol(
    price_fn,
    vega_fn,
    market_price: float,
    initial_guess: float,
    max_iter: int,
    tol: float,
    vol_min: float,
    vol_max: float,
) -> float | None:
    """Newton-Raphson with Brent fallback; None when no root in [vol_min, vol_max].

    سند §3.2: Newton-Raphson با گارد حلقه بی‌نهایت و Brent به‌عنوان روش پشتیبان.
    """
    sigma = min(max(initial_guess, vol_min), vol_max)
    for _ in range(max_iter):
        price = price_fn(sigma)
        diff = price - market_price
        if abs(diff) < tol:
            return float(sigma)
        vega = vega_fn(sigma)
        if abs(vega) < 1e-12:
            break
        sigma -= diff / vega
        if not vol_min <= sigma <= vol_max:
            break
    try:
        return float(brentq(lambda s: price_fn(s) - market_price, vol_min, vol_max, xtol=tol))
    except (ValueError, RuntimeError):
        return None


def implied_volatility_black76(
    market_price: float,
    F: float,
    K: float,
    T: float,
    r: float,
    option_type: str = "call",
    initial_guess: float = 0.30,
    max_iter: int = 100,
    tol: float = 0.001,
    vol_min: float = 0.01,
    vol_max: float = 5.0,
) -> float | None:
    """Black-76 implied volatility with arbitrage-bounds guard.

    Returns None (Null) when the market price lies outside the no-arbitrage
    bounds — i.e. violates put-call parity — or when no root converges in the
    configured search bounds. سند §3.2 + معیار پذیرش فاز ۲.
    """
    if T <= 0 or F <= 0 or K <= 0 or market_price <= 0:
        return None
    df = math.exp(-r * T)
    if option_type == "call":
        lo, hi = max(0.0, df * (F - K)), df * F
    else:
        lo, hi = max(0.0, df * (K - F)), df * K
    if market_price < lo - tol or market_price > hi + tol:
        return None

    def price_fn(s: float) -> float:
        return black76_call(F, K, T, r, s) if option_type == "call" else black76_put(F, K, T, r, s)

    def vega_fn(s: float) -> float:
        d1 = (math.log(F / K) + 0.5 * s**2 * T) / (s * math.sqrt(T))
        return math.exp(-r * T) * F * stats.norm.pdf(d1) * math.sqrt(T)

    return _solve_implied_vol(price_fn, vega_fn, market_price, initial_guess, max_iter, tol, vol_min, vol_max)


# ── Futures / physical commodity (§3.4) ────────────────────────────────────


def fair_futures_price(spot: float, risk_free: float, carry_cost: float, convenience_yield: float, T: float) -> float:
    """Tier-1 cost-of-carry fair futures: F* = S · e^((r + c − y)·T).

    c شامل تأمین مالی، انبارداری، بیمه و حمل؛ y بازده راحتی (Convenience Yield).
    """
    if T <= 0 or spot <= 0:
        return spot
    return float(spot * math.exp((risk_free + carry_cost - convenience_yield) * T))


def futures_mispricing_pct(market_futures: float, fair_futures: float) -> float:
    """Mispricing% = (F_market − F*) / F* — سند §3.4."""
    if fair_futures <= 0:
        return 0.0
    return float((market_futures - fair_futures) / fair_futures)


def intervention_risk_multiplier(price: float, band_floor: float, band_ceiling: float, steepness: float = 2.0) -> float:
    """Exponential safety factor as price nears the daily intervention band.

    سند §3.4: هرچه فاصله قیمت تا سقف/کف روزانه کمتر شود، ضریب ایمنی به‌صورت
    تصاعدی افزایش می‌یابد تا سیگنال در نزدیکی محدوده‌های دستوری صادر نشود.
    = 1.0 at mid-band, → ∞ at the band edges; inf when outside the band.
    """
    if band_ceiling <= band_floor or price <= band_floor or price >= band_ceiling:
        return float("inf")
    half = (band_ceiling - band_floor) / 2.0
    dist = min(price - band_floor, band_ceiling - price)
    if dist <= 0:
        return float("inf")
    ratio = half / dist  # 1 at mid-band → ∞ at edges
    return float(math.exp(steepness * (ratio - 1.0)))
