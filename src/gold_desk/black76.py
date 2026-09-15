"""Black-76 — قیمت‌گذاری اختیار معامله (Options) روی صندوق‌های طلا.

از سند مرجع GapGPT بخش ۳:
d1 = (ln(F/K) + 0.5*σ²*T) / (σ*√T)
d2 = d1 - σ*√T
C = e^(-rT) × [F × N(d1) - K × N(d2)]
P = e^(-rT) × [K × N(-d2) - F × N(-d1)]

F = قیمت آتی/دارایی پایه
K = قیمت اعمال
T = زمان تا سررسید (سال)
r = نرخ بهره بدون ریسک
σ = نوسان‌پذیری ضمنی

نرخ بهره ایران: ~30% (اخزا)
نوسان ضمنی صندوق طلا: ~25% سالانه
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from scipy.stats import norm

# نرخ بهره بدون ریسک ایران (تقریبی)
IRAN_RISK_FREE_RATE: float = 0.30

# نوسان ضمنی پیش‌فرض صندوق‌های طلا (سالانه)
DEFAULT_IV: float = 0.25


@dataclass(frozen=True)
class OptionGreeks:
    """یونانی‌های Black-76."""

    delta: float
    gamma: float
    vega: float  # per 1% IV
    theta: float  # per day
    rho: float  # per 1% rate


@dataclass(frozen=True)
class OptionPrice:
    """خروجی Black-76."""

    call: float
    put: float
    forward: float
    strike: float
    time_to_expiry_years: float
    iv: float
    rate: float
    d1: float
    d2: float
    greeks: OptionGreeks


def years_to_expiry(expiry: date) -> float:
    """تعداد سال تا سررسید."""
    today = date.today()
    delta_days = (expiry - today).days
    return max(delta_days / 365.0, 1e-6)  # حداقل 1 روز


def black76_price(
    forward: float,
    strike: float,
    time_years: float,
    iv: float = DEFAULT_IV,
    rate: float = IRAN_RISK_FREE_RATE,
) -> tuple[float, float, float, float]:
    """محاسبه Call و Put.

    Returns: (call, put, d1, d2)
    """
    if forward <= 0 or strike <= 0:
        raise ValueError(f"forward and strike must be > 0: F={forward}, K={strike}")
    if time_years <= 0:
        raise ValueError(f"time_years must be > 0: {time_years}")
    if iv <= 0:
        raise ValueError(f"iv must be > 0: {iv}")

    sqrt_t = math.sqrt(time_years)
    d1 = (math.log(forward / strike) + 0.5 * iv * iv * time_years) / (iv * sqrt_t)
    d2 = d1 - iv * sqrt_t

    discount = math.exp(-rate * time_years)
    call = discount * (forward * norm.cdf(d1) - strike * norm.cdf(d2))
    put = discount * (strike * norm.cdf(-d2) - forward * norm.cdf(-d1))

    return call, put, d1, d2


def black76_greeks(
    forward: float,
    strike: float,
    time_years: float,
    iv: float = DEFAULT_IV,
    rate: float = IRAN_RISK_FREE_RATE,
) -> OptionGreeks:
    """محاسبه Greeks."""
    sqrt_t = math.sqrt(time_years)
    d1 = (math.log(forward / strike) + 0.5 * iv * iv * time_years) / (iv * sqrt_t)
    d2 = d1 - iv * sqrt_t

    discount = math.exp(-rate * time_years)
    pdf_d1 = norm.pdf(d1)

    delta = discount * norm.cdf(d1)  # Call delta
    gamma = discount * pdf_d1 / (forward * iv * sqrt_t)
    # vega per 1% IV change
    vega = discount * forward * pdf_d1 * sqrt_t / 100.0
    # theta per day (سالانه / 365)
    theta = (
        -forward * pdf_d1 * iv * discount / (2 * sqrt_t)
        - rate * forward * norm.cdf(d1) * discount
        + rate * strike * norm.cdf(d2) * discount
    ) / 365.0
    # rho per 1% rate change
    rho = -time_years * (forward * norm.cdf(d1) - strike * norm.cdf(d2)) * discount / 100.0

    return OptionGreeks(delta=delta, gamma=gamma, vega=vega, theta=theta, rho=rho)


def price_option(
    forward: float,
    strike: float,
    expiry: date,
    iv: float = DEFAULT_IV,
    rate: float = IRAN_RISK_FREE_RATE,
) -> OptionPrice:
    """API ساده: تاریخ سررسید به جای سال."""
    t = years_to_expiry(expiry)
    call, put, d1, d2 = black76_price(forward, strike, t, iv, rate)
    greeks = black76_greeks(forward, strike, t, iv, rate)
    return OptionPrice(
        call=call,
        put=put,
        forward=forward,
        strike=strike,
        time_to_expiry_years=t,
        iv=iv,
        rate=rate,
        d1=d1,
        d2=d2,
        greeks=greeks,
    )


# ── استراتژی‌های protective ──────────────────────────────────────


@dataclass(frozen=True)
class CollarResult:
    """نتیجه Protective Collar."""

    cost: float  # هزینه خالص (مثبت = پرداختی، منفی = دریافتی)
    floor: float  # کف قیمت
    cap: float  # سقف قیمت
    put_premium: float
    call_premium: float
    spot: float
    put_strike: float
    call_strike: float
    time_years: float


def protective_collar(
    spot: float,
    put_strike: float,
    call_strike: float,
    expiry: date,
    iv: float = DEFAULT_IV,
    rate: float = IRAN_RISK_FREE_RATE,
) -> CollarResult:
    """استراتژی Protective Collar.

    - نگهداری دارایی پایه (spot)
    - خرید Put (حمایل نزولی) در K1
    - فروش Call (پرداخت premium) در K2 > K1

    بستن کریدور سود/زیان با هزینه خالص نزدیک صفر.
    """
    t = years_to_expiry(expiry)
    # فرض F ≈ spot (shorter expiry, no div)
    put_price, _, _, _ = black76_price(spot, put_strike, t, iv, rate)
    _, call_price, _, _ = black76_price(spot, call_strike, t, iv, rate)
    return CollarResult(
        cost=put_price - call_price,
        floor=put_strike,
        cap=call_strike,
        put_premium=put_price,
        call_premium=call_price,
        spot=spot,
        put_strike=put_strike,
        call_strike=call_strike,
        time_years=t,
    )
