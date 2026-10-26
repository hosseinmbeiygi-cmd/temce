"""Pricer — fair_value برای هر asset (طلای وزنی + سکه).

فرمول پایه:
  base_24k_per_gram = (xau_usd * usd_irt) / TROY_OUNCE_GRAMS
  fair_value(asset) = base_24k_per_gram * (purity / 24K) * weight + minting_cost (سکه)

همه توابع pure، بدون side effect، بدون DB.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

try:
    from services.gold.constants import (
        COIN_MINTING_COSTS,
        COIN_WEIGHTS,
        GOLD_PURITY_18K,
        GOLD_PURITY_24K,
        GOLD_PURITY_COIN,
        MESGHAL_GRAMS,
        MINTING_COST_TOMAN,
        TROY_OUNCE_GRAMS,
    )
except Exception:
    from .constants import (
        COIN_MINTING_COSTS,
        COIN_WEIGHTS,
        GOLD_PURITY_18K,
        GOLD_PURITY_24K,
        GOLD_PURITY_COIN,
        MESGHAL_GRAMS,
        MINTING_COST_TOMAN,
        TROY_OUNCE_GRAMS,
    )

PriceUnit = Literal["toman", "rial", "ounce"]
TOMAN_TO_RIAL = 10.0


def round_to_rial(value: float, unit: PriceUnit = "toman") -> float:
    """گرد کردن پول به **ریال** (ROUND_HALF_UP) مستقل از واحد نمایش.

    - unit="rial"  → عدد صحیح ریال
    - unit="toman" → یک رقم اعشار (۰.۱ تومان = ۱ ریال)
    - unit="ounce" → دو رقم اعشار (سنت دلار)

    دلیل: BrsApi قیمت‌ها را تومان می‌دهد، اما قرارداد نهایی «گرد کردن ریالی»
    است؛ ۰.۱ تومان همان ۱ ریال است و دقت را به ریال نگه می‌دارد.
    """
    if unit == "rial":
        quantum = Decimal("1")
    elif unit == "toman":
        quantum = Decimal("0.1")
    elif unit == "ounce":
        quantum = Decimal("0.01")
    else:  # pragma: no cover - Literal در type checker، اینجا fail-closed
        raise ValueError(f"invalid unit: {unit!r}")
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def _mint_cost(symbol: str, unit: PriceUnit) -> float:
    """کارمزد ضرب در واحد خروجی. جدول canonical تومان است."""
    mint_toman = COIN_MINTING_COSTS.get(symbol, MINTING_COST_TOMAN)
    if unit == "toman":
        return mint_toman
    if unit == "rial":
        return mint_toman * TOMAN_TO_RIAL
    raise ValueError("coin fair value is a rial/toman amount, not ounce")


def base_24k_per_gram(xau_usd: float, usd_irt: float) -> float:
    """قیمت هر گرم طلای ۲۴ عیار به تومان."""
    if xau_usd <= 0 or usd_irt <= 0:
        raise ValueError(f"invalid input: xau={xau_usd}, usd={usd_irt}")
    return (xau_usd * usd_irt) / TROY_OUNCE_GRAMS


def purity_ratio(purity_per_mille: float) -> float:
    """کسر عیار نسبت به طلای ۲۴ عیار (۹۹۹.۹) — **تعریف واحد عیار** در موتور.

    پیش‌تر pricer از ``750/999.9`` و bubbler از ``750/1000`` استفاده می‌کرد؛ دو
    تعریف از یک کمیت با اختلاف ~۰.۰۱٪ در fair و implied_usd (E-M17).
    """
    return purity_per_mille / GOLD_PURITY_24K


def fair_gold_18k(xau_usd: float, usd_irt: float) -> float:
    """هر گرم طلای ۱۸ عیار."""
    return base_24k_per_gram(xau_usd, usd_irt) * purity_ratio(GOLD_PURITY_18K)


def fair_gold_24k(xau_usd: float, usd_irt: float) -> float:
    """هر گرم طلای ۲۴ عیار (معمولاً 1 گرم شمش)."""
    return base_24k_per_gram(xau_usd, usd_irt)


def fair_coin(symbol: str, xau_usd: float, usd_irt: float, unit: PriceUnit = "toman") -> float:
    """سکه — وزن × عیار ۹۰۰ × گرم ۲۴ عیار + کارمزد ضرابخانه.

    ``usd_irt`` و خروجی هم‌واحدند. جدول کارمزد canonical تومان است؛ برای
    ``unit="rial"`` کارمزد در همین تابع ×۱۰ می‌شود تا جمع دو مقیاس قاطی نشود.
    """
    weight = COIN_WEIGHTS.get(symbol)
    if weight is None:
        raise ValueError(f"unknown coin symbol: {symbol}")
    pure_gram = weight * purity_ratio(GOLD_PURITY_COIN)
    mint = _mint_cost(symbol, unit)
    return pure_gram * base_24k_per_gram(xau_usd, usd_irt) + mint


def fair_coin_breakdown(
    symbol: str, xau_usd: float, usd_irt: float, unit: PriceUnit = "toman"
) -> dict[str, float]:
    """تفکیک اجزای fair_value سکه برای نمایش شفاف."""
    weight = COIN_WEIGHTS.get(symbol)
    if weight is None:
        raise ValueError(f"unknown coin symbol: {symbol}")
    b24 = base_24k_per_gram(xau_usd, usd_irt)
    pure_gram = weight * purity_ratio(GOLD_PURITY_COIN)
    gold_value = pure_gram * b24
    mint = _mint_cost(symbol, unit)
    return {"gold_value": gold_value, "minting_cost": mint, "fair_value": gold_value + mint}


def fair_value(
    symbol: str, xau_usd: float, usd_irt: float, unit: PriceUnit = "toman"
) -> float:
    """dispatch بر اساس symbol.

    symbol: IR_GOLD_18K | IR_GOLD_24K | IR_GOLD_1G | IR_GOLD_MELTED
            | IR_COIN_EMAMI | IR_COIN_BAHAR | IR_COIN_HALF
            | IR_COIN_QUARTER | IR_COIN_1G | IR_COIN_GERAMI

    ``usd_irt`` و خروجی هم‌واحدند (تومان پیش‌فرض؛ rial با unit="rial").

    توجه: بازار «طلای آب‌شده» (IR_GOLD_MELTED) را **مثقالی** قیمت می‌زند، پس
    ارزش ذاتی آن هم باید مثقالی باشد؛ پیش‌تر یک گرم ۱۸ عیار برگردانده می‌شد و
    حباب +۳۱۲٪ تولید می‌کرد (GS-05).
    """
    if symbol == "IR_GOLD_MELTED":
        return MESGHAL_GRAMS * fair_gold_18k(xau_usd, usd_irt)
    if symbol == "IR_GOLD_18K":
        return fair_gold_18k(xau_usd, usd_irt)
    if symbol in ("IR_GOLD_24K", "IR_GOLD_1G"):
        return fair_gold_24k(xau_usd, usd_irt)
    if symbol in COIN_WEIGHTS:
        return fair_coin(symbol, xau_usd, usd_irt, unit=unit)
    raise ValueError(f"unknown symbol: {symbol}")
