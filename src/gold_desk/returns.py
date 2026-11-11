"""محاسبات بازده گزارش‌دهی — اسمی / واقعی / دلاری.

قرارداد جریان نقدی: خروج پول سرمایه‌گذار < 0، ورود پول > 0.
معادلات مطابق بخش گزارش‌دهی (سه معیار اصلاح‌شده):

    nominal P&L = ending_value + withdrawals − contributions      (withdrawals ADD)
    nominal IRR = XIRR روی جریان‌های علامت‌دار (actual/365)
    real flow   = cf × CPI(base) / CPI(date of cf)                (نسخهٔ CPI را فراخوان انتخاب می‌کند)
    USD flow    = cf_rial / FX_rial_per_usd(date)

هیچ مقدار جعلی ساخته نمی‌شود: ورودی ناقص/غیرقابل‌حل به‌جای میان‌یابی CPI، پرکردن FX
یا برگرداندن نقطهٔ مرزی XIRR، با ``ReturnsError`` رد می‌شود.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date

from scipy.optimize import brentq

Flow = tuple[date, float]

_DAYS_PER_YEAR = 365.0


class ReturnsError(ValueError):
    """جریان‌ها قابل سالانه‌سازی/تبدیل نیستند؛ مقدار جایگزین ساخته نمی‌شود."""


def _validated(flows: Sequence[Flow]) -> list[Flow]:
    """جریان‌ها را مادی می‌کند (محافظت از iterator یک‌بارمصرف) و ورودی بد را رد می‌کند."""
    materialised = list(flows)
    for d, cf in materialised:
        if not isinstance(d, date):
            raise ReturnsError(f"flow date must be a datetime.date, got {d!r}")
        if not math.isfinite(cf):
            raise ReturnsError(f"cash flow must be finite, got {cf!r} on {d}")
    return materialised


def nominal_pnl(ending_value: float, contributions: float, withdrawals: float) -> float:
    """P&L = ارزش پایانی + پول برداشت‌شده − پول واریزشده (برداشت به P&L اضافه می‌شود)."""
    return ending_value + withdrawals - contributions


def xirr(flows: Sequence[Flow], lo: float = -0.99, hi: float = 100.0) -> float:
    """بازده سالانهٔ وزنی‌پول (actual/365) روی جریان‌های علامت‌دار.

    نیازمند حداقل یک ورود و یک خروج پول است (وگرنه IRR تعریف نشده) و تغییر علامت NPV
    روی (lo, hi)؛ در غیر این صورت ``ReturnsError`` بالا می‌رود.
    """
    if not math.isfinite(lo) or not math.isfinite(hi) or lo >= hi:
        raise ReturnsError(f"invalid rate bracket lo={lo!r} hi={hi!r}")
    flows = _validated(flows)
    if not any(cf < 0 for _, cf in flows) or not any(cf > 0 for _, cf in flows):
        raise ReturnsError("XIRR undefined: flows need at least one outflow and one inflow")
    t0 = min(d for d, _ in flows)

    def npv(r: float) -> float:
        total = 0.0
        for d, cf in flows:
            total += cf / (1.0 + r) ** ((d - t0).days / _DAYS_PER_YEAR)
        return total

    fa, fb = npv(lo), npv(hi)
    if not math.isfinite(fa) or not math.isfinite(fb):
        raise ReturnsError("XIRR objective is not finite over the bracket")
    if fa == 0.0:
        return lo
    if fb == 0.0:
        return hi
    if fa * fb > 0.0:
        raise ReturnsError(f"no sign change on ({lo}, {hi}); IRR outside the bracket - widen lo/hi")
    return float(brentq(npv, lo, hi))


def _level(series: Mapping[date, float], on: date, name: str) -> float:
    """سطح CPI/FX برای یک تاریخ؛ غایب یا نامثبت ⇒ ReturnsError."""
    if on not in series:
        raise ReturnsError(f"{name} has no value for {on}")
    value = series[on]
    if not math.isfinite(value) or value <= 0:
        raise ReturnsError(f"{name} at {on} must be positive and finite, got {value!r}")
    return value


def deflate(flows: Sequence[Flow], cpi: Mapping[date, float], base: date) -> list[Flow]:
    """جریان‌ها به پول تاریخ پایه: cf × CPI(base) / CPI(d). نسخهٔ CPI را فراخوان انتخاب می‌کند."""
    cpi_base = _level(cpi, base, "CPI (base)")
    return [(d, cf * cpi_base / _level(cpi, d, "CPI")) for d, cf in _validated(flows)]


def to_usd(flows: Sequence[Flow], fx_rial_per_usd: Mapping[date, float]) -> list[Flow]:
    """USD flow = cf_rial / FX_rial_per_usd(date)؛ نرخ باید مثبت و ریال‌به‌دلار باشد."""
    return [(d, cf / _level(fx_rial_per_usd, d, "FX")) for d, cf in _validated(flows)]
