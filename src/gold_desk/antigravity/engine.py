"""Engine — موتور واحد implicit/implied calculations.

Motive: Contains the core calculation logic for:
- Pure gold 18k: (XAU_USD * USD_IRR / 31.1035) * 0.75
- Coin intrinsic: weight * purity * base_24k + minting_cost
- Bubble %: (market - fair) / fair * 100
- Implied USD from inverse market price

All functions are pure, no side effects, no DB access.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from ..constants import COIN_WEIGHTS, TROY_OUNCE_GRAMS
from ..pricer import PriceUnit, fair_coin, fair_value, round_to_rial
from ..pricer import fair_gold_18k as _pricer_gold_18k

# مقادیر مجاز قرارداد — "mixed" و "fallback" عمداً رد می‌شوند (fail-closed).
ALLOWED_SOURCES = frozenset({"brsapi", "tgju", "cache"})
ALLOWED_QUALITIES = frozenset({"LIVE", "DELAYED", "SAMPLE", "EDUCATIONAL"})
ALLOWED_UNITS = frozenset({"toman", "rial", "ounce"})


def calculate_pure_gold_18k(xau_usd: float, usd_irt: float) -> float:
    """گرم ۱۸: (XAU_USD * USD_IRR / 31.1035) * (750 / 999.9) ≈ × 0.75

    واحد موتور = همان pricer.fair_gold_18k؛ عیار فقط **یک بار** اعمال می‌شود.
    پیش‌تر ``purity_ratio(...) * 0.75`` هر دو زده می‌شد و خروجی ۲۵٪ کمتر از
    موتور کانونیکال بود (E-01). این تابع اکنون delegate است؛ حذف نشده تا
    مصرف‌کننده‌های قبلی نشکنند.

    تابع نسبت به مقیاس بی‌طرف است: اگر ``usd_irt`` ریال باشد خروجی ریال است،
    اگر تومان باشد خروجی تومان. قرارداد snapshot از تومان استفاده می‌کند چون
    BrsApi نفسه ``unit="تومان"`` می‌دهد.
    """
    if xau_usd <= 0 or usd_irt <= 0:
        raise ValueError(f"invalid input: xau={xau_usd}, usd={usd_irt}")
    return _pricer_gold_18k(xau_usd, usd_irt)


def calculate_coin_intrinsic(
    symbol: str, xau_usd: float, usd_irt: float, unit: PriceUnit = "toman"
) -> float:
    """ارزش inherent یک سکه: weight × purity × base_24k + minting_cost.

    فرمول پایه (از pricer.fair_coin):
      fair = weight * (purity / 999.9) * base_24k_per_gram + minting_cost

    ``unit`` هم واحد ورودی ``usd_irt`` است و هم واحد خروجی؛ کارمزد جدول
    canonical تومان است و برای ریال ×۱۰ می‌شود.
    """
    if xau_usd <= 0 or usd_irt <= 0:
        raise ValueError(f"invalid input: xau={xau_usd}, usd={usd_irt}")
    if symbol not in COIN_WEIGHTS:
        raise ValueError(f"unknown coin symbol: {symbol}")
    return fair_coin(symbol, xau_usd, usd_irt, unit=unit)


def calculate_bubble_abs(market: float, fair: float) -> float | None:
    """حباب مقداری = market − intrinsic (هم‌واحد ورودی‌ها)."""
    if fair <= 0:
        return None
    return market - fair


def calculate_bubble_pct(market: float, fair: float) -> float | None:
    """محاسبه درصد حباب: ((بازار -ذاتی) /ذاتی) * 100

    Returns None if fair <= 0 (invalid input).
    """
    if fair <= 0:
        return None
    return ((market - fair) / fair) * 100.0


def calculate_implied_usd(market: float, symbol: str, xau_usd: float) -> float | None:
    """implied USD = دلاری که در قیمت بازار Nahفته است.

    فرمول: (market * 31.1035) / (pure_w * xau_usd)
    که market = قیمت هر واحد (گرم/مثقال) و pure_w = وزن طلای خالص همان واحد.
    خروجی هم‌واحد market است (تومان/دلار یا ریال/دلار).
    """
    if xau_usd <= 0:
        return None
    from ..bubbler import _pure_gold_weight

    pure_w = _pure_gold_weight(symbol)
    if pure_w <= 0:
        return None
    return (market * TROY_OUNCE_GRAMS) / (pure_w * xau_usd)


def calculate_snapshot_fields(
    xau_usd: float,
    usd_irt: float,
    market_price: float,
    symbol: str,
    *,
    source: Literal["brsapi", "tgju", "cache"] = "brsapi",
    quality: Literal["LIVE", "DELAYED", "SAMPLE", "EDUCATIONAL"] = "DELAYED",
    as_of: datetime | None = None,
    unit: PriceUnit = "toman",
) -> dict[str, object]:
    """Calculate all required snapshot fields per contract.

    Returns dict with: value, unit, asOf, source, quality (+ bubble fields).

    ``source``/``quality``/``as_of``/``unit`` را caller تعیین می‌کند؛ مقدار
    پیش‌فرض quality=DELAYED است تا داده‌ای که تازگی‌اش اثبات نشده LIVE برچسب
    نخورد. ``value`` به ریال گرد می‌شود (ROUND_HALF_UP) و ``unit`` واحد
    ورودی/خروجی است.
    """
    if source not in ALLOWED_SOURCES:
        raise ValueError(f"invalid source: {source!r}")
    if quality not in ALLOWED_QUALITIES:
        raise ValueError(f"invalid quality: {quality!r}")
    if unit not in ALLOWED_UNITS:
        raise ValueError(f"invalid unit: {unit!r}")
    if unit == "ounce":
        # ارزش ذاتی این دارایی‌ها ریال/تومان است؛ «اونس» برای مرجع XAU است، نه
        # برای fair_value. واحد اشتباه نباید عدد بی‌معنا تولید کند (fail-closed).
        raise ValueError("asset fair value unit must be toman or rial, not ounce")

    fair = fair_value(symbol, xau_usd, usd_irt, unit=unit)
    bubble_pct = calculate_bubble_pct(market_price, fair)
    bubble_abs = calculate_bubble_abs(market_price, fair)
    implied_usd = calculate_implied_usd(market_price, symbol, xau_usd)

    return {
        "value": round_to_rial(fair, unit),
        "unit": unit,
        "asOf": (as_of or datetime.now(UTC)).isoformat(),
        "source": source,
        "quality": quality,
        "bubble_abs": round_to_rial(bubble_abs, unit) if bubble_abs is not None else None,
        "bubble_pct": bubble_pct,
        "implied_usd": implied_usd,
    }


def fair_gold_18k(xau_usd: float, usd_irt: float) -> float:
    """Each gram of 18k gold — delegate به موتور کانونیکال pricer."""
    return _pricer_gold_18k(xau_usd, usd_irt)
