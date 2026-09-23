"""Higher-order Greeks computation for options.

Extends the basic Greeks (delta, gamma, theta, vega, rho) with:
- Speed: dGamma/dS (sensitivity of gamma to spot price changes)
- Charm: dDelta/dT (delta decay over time, also called delta bleed)
- Vanna: dDelta/dSigma (sensitivity of delta to volatility changes)
- Vomma: dVega/dSigma (sensitivity of vega to volatility, also called volga)
- Ultima: dVomma/dSigma
- Color: dGamma/dT (gamma decay over time)

Used for dynamic hedging and risk management of options portfolios.
"""
from __future__ import annotations

import math

from scipy import stats


def _bs_d1(S: float, K: float, T: float, r: float, sigma: float) -> float:
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0
    return (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))


def _bs_d2(d1: float, sigma: float, T: float) -> float:
    return d1 - sigma * math.sqrt(T)


def speed(S: float, K: float, T: float, r: float, sigma: float, option_type: str = "call") -> float:
    """Speed: third-order Greek. dGamma/dS = -gamma / S * (d1/(sigma*sqrt(T)) + 1).

    Measures the rate of change of gamma with respect to changes in the underlying price.
    Important for delta-hedging in volatile markets.
    """
    if T <= 0 or sigma <= 0 or S <= 0:
        return 0.0
    import math as _m

    d1 = _bs_d1(S, K, T, r, sigma)
    _den = S * sigma * _m.sqrt(T)
    if not _m.isfinite(_den) or _den < 1e-12:
        return 0.0
    gamma_val = stats.norm.pdf(d1) / _den
    out = float(-gamma_val / S * (d1 / (sigma * _m.sqrt(T)) + 1))
    return out if _m.isfinite(out) else 0.0


def charm(S: float, K: float, T: float, r: float, sigma: float, option_type: str = "call") -> float:
    """Charm: dDelta/dT (delta decay per unit time).

    Also called "delta bleed" or "delta decay". Implemented for the
    zero-dividend-yield case (q = 0), which matches the TSE options market
    where the underlying has no dividend yield:
    For call: charm = -N'(d1) * (r/(sigma*sqrt(T)) - d2/(2*T))
    For put:  charm = +N'(d1) * (r/(sigma*sqrt(T)) - d2/(2*T))
    """
    if T <= 0 or sigma <= 0 or S <= 0:
        return 0.0
    d1 = _bs_d1(S, K, T, r, sigma)
    d2 = d1 - sigma * math.sqrt(T)
    npdf_d1 = stats.norm.pdf(d1)
    sqrt_T = math.sqrt(T)

    if option_type == "call":
        return float(-(npdf_d1 * (r / (sigma * sqrt_T) - d2 / (2 * T))))
    else:
        return float(npdf_d1 * (r / (sigma * sqrt_T) - d2 / (2 * T)))


def vanna(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Vanna: dDelta/dSigma = dVega/dS.

    Measures sensitivity of delta to changes in implied volatility.
    Important for vol-gamma trading.
    Vanna = -N'(d1) * d2 / sigma
    """
    if T <= 0 or sigma <= 0 or S <= 0:
        return 0.0
    d1 = _bs_d1(S, K, T, r, sigma)
    d2 = d1 - sigma * math.sqrt(T)
    return float(-stats.norm.pdf(d1) * d2 / sigma)


def vomma(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Vomma: dVega/dSigma = d2V/dSigma2.

    Also called "volga" or "volconv". Measures sensitivity of vega to changes in volatility.
    Important for vega-hedging.
    Vomma = Vega * d1 * d2 / sigma
    """
    if T <= 0 or sigma <= 0 or S <= 0:
        return 0.0
    d1 = _bs_d1(S, K, T, r, sigma)
    d2 = d1 - sigma * math.sqrt(T)
    vega_val = S * stats.norm.pdf(d1) * math.sqrt(T) / 100.0
    return float(vega_val * d1 * d2 / sigma)


def color(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Color: dGamma/dT (gamma decay per unit time).

    Measures how gamma changes as time passes.
    Important for managing gamma risk near expiry.
    """
    if T <= 0 or sigma <= 0 or S <= 0:
        return 0.0
    import math as _m

    d1 = _bs_d1(S, K, T, r, sigma)
    d2 = d1 - sigma * _m.sqrt(T)
    _den = S * sigma * _m.sqrt(T)
    if not _m.isfinite(_den) or _den < 1e-12:
        return 0.0
    gamma_val = stats.norm.pdf(d1) / _den
    out = float(-gamma_val * (
        r + (r - 0.5 * sigma**2) * d1 / (sigma * _m.sqrt(T))
        + (1 - d1 * d2) / (2 * T)
    ))
    return out if _m.isfinite(out) else 0.0


def ultima(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Ultima: dVomma/dSigma.

    Third-order sensitivity of vega to volatility.
    Used for advanced vega-hedging strategies.
    """
    if T <= 0 or sigma <= 0 or S <= 0:
        return 0.0
    d1 = _bs_d1(S, K, T, r, sigma)
    d2 = d1 - sigma * math.sqrt(T)
    vomma_val = vomma(S, K, T, r, sigma)
    return float(vomma_val / sigma * (d1 * d2 / sigma**2 - 1 - 2 * d1 * d2 / sigma**2))


def compute_all_higher_order_greeks(
    S: float, K: float, T: float, r: float, sigma: float, option_type: str = "call"
) -> dict[str, float]:
    """Compute all higher-order Greeks for given parameters.

    Returns dict with speed, charm, vanna, vomma, color, ultima.
    """
    return {
        "speed": speed(S, K, T, r, sigma, option_type),
        "charm": charm(S, K, T, r, sigma, option_type),
        "vanna": vanna(S, K, T, r, sigma),
        "vomma": vomma(S, K, T, r, sigma),
        "color": color(S, K, T, r, sigma),
        "ultima": ultima(S, K, T, r, sigma),
    }
