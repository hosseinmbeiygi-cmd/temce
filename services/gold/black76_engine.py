"""موتور Black-76 — قیمت‌گذاری، یونانی‌ها و نوسان ضمنی اختیار معاملهٔ کالایی.

قیمت‌گذاری روی قیمت آتی/فوروارد (F) انجام می‌شود، نه اسپات:

    d1 = (ln(F/K) + 0.5σ²T) / (σ√T)
    d2 = d1 - σ√T
    Call = e^(-rT) [F N(d1) - K N(d2)]
    Put  = e^(-rT) [K N(-d2) - F N(-d1)]

در سررسید (T → 0) قیمت برابر ارزش ذاتی تنزیل‌شده است و فرمول حدی
استفاده می‌شود تا تقسیم بر صفر رخ ندهد.

همهٔ توابع pure هستند: بدون DB، بدون I/O و بدون side effect.
"""

from __future__ import annotations

import math
from typing import Any

from scipy.optimize import brentq
from scipy.stats import norm

# آستانهٔ «سررسیدشده» — پایین‌تر از این مقدار، فرمول حدی اعمال می‌شود.
T_MIN: float = 1e-12

# بازهٔ جست‌وجوی نوسان ضمنی: ۰٫۰۱٪ تا ۵۰۰٪
IV_LOWER_BOUND: float = 1e-4
IV_UPPER_BOUND: float = 5.0
IV_PRICE_TOLERANCE: float = 1e-10

_OPTION_TYPES = ("call", "put")


def _validate_option_type(option_type: str) -> str:
    """نرمال‌سازی و اعتبارسنجی نوع اختیار معامله."""
    if not isinstance(option_type, str):
        raise ValueError(f"option_type must be 'call' or 'put', got {option_type!r}")
    normalized = option_type.strip().lower()
    if normalized not in _OPTION_TYPES:
        raise ValueError(
            f"option_type must be 'call' or 'put', got {option_type!r}"
        )
    return normalized


def _require_positive(name: str, value: float) -> None:
    if value is None or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive number, got {value!r}")


def _require_non_negative(name: str, value: float) -> None:
    if value is None or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite non-negative number, got {value!r}")


def _validate_inputs(F: float, K: float, T: float, r: float, sigma: float) -> None:
    _require_positive("F", F)
    _require_positive("K", K)
    _require_non_negative("T", T)
    _require_non_negative("r", r)
    _require_positive("sigma", sigma)


def _d1_d2(F: float, K: float, T: float, sigma: float) -> tuple[float, float, float]:
    sqrt_t = math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * sigma * sigma * T) / (sigma * sqrt_t)
    return d1, d1 - sigma * sqrt_t, sqrt_t


def _intrinsic(F: float, K: float, T: float, r: float, option_type: str) -> float:
    discount = math.exp(-r * T)
    if option_type == "call":
        return max(0.0, F - K) * discount
    return max(0.0, K - F) * discount


def black76_price(
    F: float, K: float, T: float, r: float, sigma: float, option_type: str
) -> float:
    """قیمت اختیار معاملهٔ اروپایی روی F با مدل Black-76.

    ``option_type`` می‌تواند ``"call"`` یا ``"put"`` (بدون حساسیت به حروف)
    باشد. برای ``T <= 0`` ارزش ذاتی تنزیل‌شده برگردانده می‌شود.
    """
    option_type = _validate_option_type(option_type)
    _validate_inputs(F, K, T, r, sigma)

    if T <= T_MIN:
        return _intrinsic(F, K, T, r, option_type)

    d1, d2, _ = _d1_d2(F, K, T, sigma)
    discount = math.exp(-r * T)

    if option_type == "call":
        return discount * (F * norm.cdf(d1) - K * norm.cdf(d2))
    return discount * (K * norm.cdf(-d2) - F * norm.cdf(-d1))


def calculate_greeks(
    F: float, K: float, T: float, r: float, sigma: float, option_type: str
) -> dict[str, float]:
    """یونانی‌های تحلیلی Black-76.

    مقادیر پایهٔ ریاضی برگردانده می‌شوند:
      • ``vega`` برای ۱٫۰۰ واحد تغییر نوسان و ``vega_pct`` برای ۱٪.
      • ``theta`` سالانه و ``theta_daily`` روزانه (÷۳۶۵).
      • ``rho = -T * price``.

    در سررسید، گاما/وگا/تتا صفر و دلتا فقط جهت ارزش ذاتی را نشان می‌دهد.
    """
    option_type = _validate_option_type(option_type)
    _validate_inputs(F, K, T, r, sigma)

    if T <= T_MIN:
        # In the expiry limit only the intrinsic direction remains.
        delta = (
            (1.0 if F > K else 0.0)
            if option_type == "call"
            else (-1.0 if F < K else 0.0)
        )
        price = _intrinsic(F, K, T, r, option_type)
        return {
            "delta": delta,
            "gamma": 0.0,
            "vega": 0.0,
            "vega_pct": 0.0,
            "theta": 0.0,
            "theta_daily": 0.0,
            "rho": -T * price,
        }

    d1, d2, sqrt_t = _d1_d2(F, K, T, sigma)
    discount = math.exp(-r * T)
    pdf_d1 = norm.pdf(d1)
    cdf_d1 = norm.cdf(d1)
    cdf_d2 = norm.cdf(d2)

    gamma = discount * pdf_d1 / (F * sigma * sqrt_t)
    vega = F * discount * pdf_d1 * sqrt_t
    time_decay = -(F * discount * pdf_d1 * sigma) / (2.0 * sqrt_t)

    if option_type == "call":
        price = discount * (F * cdf_d1 - K * cdf_d2)
        delta = discount * cdf_d1
    else:
        price = discount * (K * norm.cdf(-d2) - F * norm.cdf(-d1))
        delta = -discount * norm.cdf(-d1)

    # θ = ∂V/∂t = -∂V/∂T = time_decay + r·V for both call and put: the
    # diffusion term is identical and only the discounting carries the
    # risk-free rate (audit FIN-01). The previous call branch added an extra
    # +r·F·e^{-rT}·N(d1) term and the put branch used -r·V, which flipped the
    # sign of theta in normal regimes. Locked by
    # tests/unit/services/test_black76_theta_derivative.py against -dV/dT.
    theta = time_decay + r * price

    return {
        "delta": delta,
        "gamma": gamma,
        "vega": vega,
        "vega_pct": vega / 100.0,
        "theta": theta,
        "theta_daily": theta / 365.0,
        "rho": -T * price,
    }


def _bisection(
    func: Any, lower: float, upper: float, tol: float = IV_PRICE_TOLERANCE
) -> float:
    """جست‌وجوی ریشهٔ جایگزین وقتی brentq در دسترس یا همگرا نیست."""
    f_lower = func(lower)
    for _ in range(200):
        middle = 0.5 * (lower + upper)
        f_middle = func(middle)
        if abs(f_middle) < tol or (upper - lower) / 2.0 < tol:
            return middle
        if (f_lower < 0.0) == (f_middle < 0.0):
            lower, f_lower = middle, f_middle
        else:
            upper = middle
    return 0.5 * (lower + upper)


def implied_volatility(
    market_price: float, F: float, K: float, T: float, r: float, option_type: str
) -> float:
    """استخراج نوسان ضمنی با brentq روی بازهٔ ``[1e-4, 5.0]``.

    اگر قیمت بازار از کران پایین (ارزش ذاتی تنزیل‌شده) یا کران بالای
    نظری عبور کند، ``ValueError`` داده می‌شود؛ در صورت شکست همگرایی
    brentq، روش دوبخشی جایگزین می‌شود.
    """
    option_type = _validate_option_type(option_type)
    _require_positive("market_price", market_price)
    _require_positive("F", F)
    _require_positive("K", K)
    _require_positive("T", T)
    _require_non_negative("r", r)

    lower_bound = _intrinsic(F, K, T, r, option_type)
    if market_price <= lower_bound:
        raise ValueError("Price violates lower arbitrage bound")

    def difference(sigma: float) -> float:
        return black76_price(F, K, T, r, sigma, option_type) - market_price

    f_lower = difference(IV_LOWER_BOUND)
    f_upper = difference(IV_UPPER_BOUND)
    if f_lower > 0.0:
        raise ValueError("Price violates lower arbitrage bound")
    if f_upper < 0.0:
        raise ValueError("Price violates upper arbitrage bound")

    try:
        return float(
            brentq(
                difference,
                IV_LOWER_BOUND,
                IV_UPPER_BOUND,
                xtol=IV_PRICE_TOLERANCE,
                rtol=1e-12,
                maxiter=200,
            )
        )
    except (ValueError, RuntimeError):
        return _bisection(difference, IV_LOWER_BOUND, IV_UPPER_BOUND)
