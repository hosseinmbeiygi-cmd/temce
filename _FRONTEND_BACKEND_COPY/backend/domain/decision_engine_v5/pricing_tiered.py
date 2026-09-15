"""Tiered Pricing — v5.0 Research Plane — Black-76 / Displaced Diffusion / SABR gate."""

from __future__ import annotations

import math

from scipy import stats
from scipy.optimize import brentq


# ── Tier 1: Black-76 (سند §4.1) ──
def black76_price(F: float, K: float, T: float, r: float, sigma: float, is_call: bool = True) -> float:
    """Black-76: C = e^-rT [F N(d1) - K N(d2)], d1=[ln(F/K)+0.5σ²T]/(σ√T), d2=d1-σ√T."""
    if T <= 0 or sigma <= 0 or F <= 0 or K <= 0:
        return max(0.0, F - K) if is_call else max(0.0, K - F)
    d1 = (math.log(F / K) + 0.5 * sigma * sigma * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    df = math.exp(-r * T)
    if is_call:
        return df * (F * stats.norm.cdf(d1) - K * stats.norm.cdf(d2))
    return df * (K * stats.norm.cdf(-d2) - F * stats.norm.cdf(-d1))


def black76_greeks(F: float, K: float, T: float, r: float, sigma: float, is_call: bool = True) -> dict[str, float]:
    d1 = (math.log(F / K) + 0.5 * sigma * sigma * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    df = math.exp(-r * T)
    nd1 = stats.norm.cdf(d1)
    pdf_d1 = stats.norm.pdf(d1)
    delta = df * nd1 if is_call else df * (nd1 - 1)
    gamma = df * pdf_d1 / (F * sigma * math.sqrt(T))
    vega = F * df * pdf_d1 * math.sqrt(T)
    return {"delta": delta, "gamma": gamma, "vega": vega, "d1": d1, "d2": d2}


# ── Tier 2: Displaced Diffusion (سند §4.1) ──
def displaced_diffusion_price(
    F: float, K: float, T: float, r: float, sigma: float, alpha: float, is_call: bool = True
) -> float:
    """Displaced Diffusion: dS = r S dt + σ(S+α) dW, C = e^-rT [(F+α)N(d1)-(K+α)N(d2)]."""
    Fa = F + alpha
    Ka = K + alpha
    if Fa <= 0 or Ka <= 0:
        return black76_price(F, K, T, r, sigma, is_call)
    d1 = (math.log(Fa / Ka) + 0.5 * sigma * sigma * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    df = math.exp(-r * T)
    if is_call:
        return df * (Fa * stats.norm.cdf(d1) - Ka * stats.norm.cdf(d2))
    return df * (Ka * stats.norm.cdf(-d2) - Fa * stats.norm.cdf(-d1))


# ── IV: Newton-Raphson + Brent fallback (سند §4.2) ──
def implied_volatility(
    market_price: float,
    F: float,
    K: float,
    T: float,
    r: float,
    is_call: bool = True,
    tol: float = 1e-6,
    max_iter: int = 50,
) -> float | None:
    """IV با Newton-Raphson، fallback به Brent. بازگشت None اگر همگرا نشود یا Put-Call Parity نقض شود."""
    sigma = 0.3
    for _ in range(max_iter):
        model = black76_price(F, K, T, r, sigma, is_call)
        diff = model - market_price
        if abs(diff) < tol:
            return sigma
        greeks = black76_greeks(F, K, T, r, sigma, is_call)
        vega = greeks["vega"]
        if abs(vega) < 1e-12:
            break
        sigma -= diff / vega
        if not 0.01 <= sigma <= 3.0:
            break
    # Fallback Brent
    try:
        return float(brentq(lambda s: black76_price(F, K, T, r, s, is_call) - market_price, 0.01, 3.0, xtol=tol))
    except (ValueError, RuntimeError):
        return None


# ── Cost-of-Carry Tier 1 & Tier 2 (سند §4.4) ──
def cost_of_carry_fair_price(S: float, r: float, c: float, y: float, T: float) -> float:
    """Tier1: F* = S e^((r+c-y)T). c=هزینه نگهداری، y=بازده رفاهی."""
    return S * math.exp((r + c - y) * T)


def cointegration_zscore(spread: float, mean: float, std: float) -> float:
    """Tier2: Z = (Spread - μ)/σ, سیگنال |Z|>2."""
    if std < 1e-9:
        return 0.0
    return (spread - mean) / std


# ── SABR Gate (سند §4.2) ─
def sabr_gate(
    strikes_per_maturity: dict[str, list[float]],
    calibration_rmse: float | None,
    calibrated_days: int,
) -> tuple[bool, list[str]]:
    """بازگشت (مجاز؟, دلایل). Tier1 تا زمانی که Gate پاس نشود فعال می‌ماند."""
    reasons: list[str] = []
    for mat, strikes in strikes_per_maturity.items():
        if len(strikes) < 5:
            reasons.append(f"{mat}: {len(strikes)} <5 strikes")
    if len(strikes_per_maturity) < 2:
        reasons.append(f"{len(strikes_per_maturity)} maturities <2")
    if calibration_rmse is None or calibration_rmse >= 0.02:
        reasons.append(f"RMSE {calibration_rmse} >=0.02")
    if calibrated_days < 20:
        reasons.append(f"stability {calibrated_days}d <20d")
    return (not reasons, reasons)
