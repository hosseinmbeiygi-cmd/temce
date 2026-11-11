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

from core.time import now_tehran

# نرخ بهره بدون ریسک ایران (تقریبی)
IRAN_RISK_FREE_RATE: float = 0.30

# نوسان ضمنی پیش‌فرض صندوق‌های طلا (سالانه)
DEFAULT_IV: float = 0.25

# منبع داده زنده برای options chain بورس تهران (BrsApi) هنوز تأیید نشده است.
# این ثابت وجود گپ را مستند می‌کند (WS7 — BrsApi options chain gap).
BRSAPI_OPTIONS_DEFERRED: bool = True


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
    """تعداد سال تا سررسید — مبنا **تاریخ تهران** است، نه منطقهٔ زمانی سیستم.

    پیش‌تر ``date.today()`` بود؛ روی سرور UTC، بین ۲۰:۳۰ تا ۲۴ تهران یک روز
    اختلاف می‌داد. قرارداد منقضی هم به‌جای عدد تقریباً صفر، ``ValueError`` است
    (E-L6).
    """
    today = now_tehran().date()
    delta_days = (expiry - today).days
    if delta_days < 0:
        raise ValueError(f"expiry is in the past: {expiry} < {today}")
    return max(delta_days / 365.0, 1e-6)  # حداقل ~31 ثانیه (1e-6 سال)


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
    # theta per day (سالانه / 365) - corrected formula for E-H5
    # Original had sign error: magnitude was ~3x too large.
    # Using formula that matches the finite-difference test.
    theta = (
        -forward * pdf_d1 * iv * discount / (2 * sqrt_t)
        + rate * discount * (forward * norm.cdf(d1) - strike * norm.cdf(d2))
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


def implied_volatility(
    market_price: float,
    forward: float,
    strike: float,
    time_years: float,
    rate: float = IRAN_RISK_FREE_RATE,
    option_type: str = "call",
    tol: float = 1e-8,
    max_iter: int = 200,
) -> float:
    """نوسان ضمنی (Implied Volatility) از قیمت بازار با Newton-Raphson.

    Args:
        market_price: قیمت مشاهده‌شده در بازار (> 0).
        forward: قیمت آتی یا spot.
        strike: قیمت اعمال.
        time_years: زمان تا سررسید (سال، > 0).
        rate: نرخ بهره بدون ریسک.
        option_type: "call" یا "put".
        tol: دقت همگرایی.
        max_iter: حداکثر تکرار.

    Returns:
        σ ضمنی (سالانه) در صورت همگرایی.

    Raises:
        ValueError: برای ورودی‌های نامعتبر.
        RuntimeError: اگر solver همگرا نشود.
    """
    option_type = option_type.strip().lower()
    if option_type not in ("call", "put"):
        raise ValueError(f"option_type must be 'call' or 'put', got {option_type!r}")
    if market_price <= 0:
        raise ValueError(f"market_price must be > 0: {market_price}")
    if time_years <= 0:
        raise ValueError(f"time_years must be > 0: {time_years}")
    if forward <= 0 or strike <= 0:
        raise ValueError(f"forward and strike must be > 0: F={forward}, K={strike}")

    def price_at(sigma: float) -> float:
        c, p, _, _ = black76_price(forward, strike, time_years, sigma, rate)
        return c if option_type == "call" else p

    def vega_at(sigma: float) -> float:
        sqrt_t = math.sqrt(time_years)
        d1 = (math.log(forward / strike) + 0.5 * sigma * sigma * time_years) / (sigma * sqrt_t)
        return math.exp(-rate * time_years) * forward * norm.pdf(d1) * sqrt_t

    # Newton-Raphson starting at a reasonable initial guess
    sigma = 0.30
    for _ in range(max_iter):
        p = price_at(sigma)
        diff = p - market_price
        if abs(diff) < tol:
            return sigma
        v = vega_at(sigma)
        if abs(v) < 1e-14:
            break
        sigma_new = sigma - diff / v
        if sigma_new <= 0:
            sigma_new = sigma / 2.0
        sigma = sigma_new

    # Bisection fallback
    lo, hi = 1e-6, 10.0
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        if price_at(mid) < market_price:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            return (lo + hi) / 2.0

    raise RuntimeError(
        f"implied_volatility did not converge for price={market_price}, "
        f"F={forward}, K={strike}, T={time_years}"
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
    # Black-76 is defined on the forward price, not spot.  F = spot * e^(r*t).
    # With Iran's ~30% risk-free rate, F/spot ≈ 1.16 at T=0.5 → ~16% mispricing
    # if spot were passed directly (confirmed in GS-B76 audit).
    F = spot * math.exp(rate * t)
    # black76_price returns (call, put, d1, d2) — unpack accordingly
    _, put_price, _, _ = black76_price(F, put_strike, t, iv, rate)
    call_price, _, _, _ = black76_price(F, call_strike, t, iv, rate)
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
