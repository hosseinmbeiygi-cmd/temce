"""Pricer — fair_value برای هر asset (طلای وزنی + سکه).

فرمول پایه:
  base_24k_per_gram = (xau_usd * usd_irt) / TROY_OUNCE_GRAMS
  fair_value(asset) = base_24k_per_gram * (purity / 24K) * weight + minting_cost (سکه)

همه توابع pure، بدون side effect، بدون DB.
"""

from __future__ import annotations

from .constants import (
    COIN_MINTING_COSTS,
    COIN_WEIGHTS,
    GOLD_PURITY_18K,
    GOLD_PURITY_24K,
    GOLD_PURITY_COIN,
    MINTING_COST_TOMAN,
    TROY_OUNCE_GRAMS,
)


def base_24k_per_gram(xau_usd: float, usd_irt: float) -> float:
    """قیمت هر گرم طلای ۲۴ عیار به تومان."""
    if xau_usd <= 0 or usd_irt <= 0:
        raise ValueError(f"invalid input: xau={xau_usd}, usd={usd_irt}")
    return (xau_usd * usd_irt) / TROY_OUNCE_GRAMS


def fair_gold_18k(xau_usd: float, usd_irt: float) -> float:
    """هر گرم طلای ۱۸ عیار."""
    return base_24k_per_gram(xau_usd, usd_irt) * (GOLD_PURITY_18K / GOLD_PURITY_24K)


def fair_gold_24k(xau_usd: float, usd_irt: float) -> float:
    """هر گرم طلای ۲۴ عیار (معمولاً 1 گرم شمش)."""
    return base_24k_per_gram(xau_usd, usd_irt)


def fair_coin(symbol: str, xau_usd: float, usd_irt: float) -> float:
    """سکه بهار آزادی — وزن × عیار ۹۰۰ × گرم ۲۴ عیار + کارمزد ضرابخانه تفکیکی."""
    weight = COIN_WEIGHTS.get(symbol)
    if weight is None:
        raise ValueError(f"unknown coin symbol: {symbol}")
    pure_gram = weight * (GOLD_PURITY_COIN / GOLD_PURITY_24K)
    mint = COIN_MINTING_COSTS.get(symbol, MINTING_COST_TOMAN)
    return pure_gram * base_24k_per_gram(xau_usd, usd_irt) + mint


def fair_coin_breakdown(symbol: str, xau_usd: float, usd_irt: float) -> dict[str, float]:
    """تفکیک اجزای fair_value سکه برای نمایش شفاف."""
    weight = COIN_WEIGHTS.get(symbol)
    if weight is None:
        raise ValueError(f"unknown coin symbol: {symbol}")
    b24 = base_24k_per_gram(xau_usd, usd_irt)
    pure_gram = weight * (GOLD_PURITY_COIN / GOLD_PURITY_24K)
    gold_value = pure_gram * b24
    mint = COIN_MINTING_COSTS.get(symbol, MINTING_COST_TOMAN)
    return {"gold_value": gold_value, "minting_cost": mint, "fair_value": gold_value + mint}


def fair_value(symbol: str, xau_usd: float, usd_irt: float) -> float:
    """dispatch بر اساس symbol.

    symbol: IR_GOLD_18K | IR_GOLD_24K | IR_GOLD_1G | IR_GOLD_MELTED
            | IR_COIN_EMAMI | IR_COIN_BAHAR | IR_COIN_HALF
            | IR_COIN_QUARTER | IR_COIN_1G | IR_COIN_GERAMI
    """
    if symbol in ("IR_GOLD_18K", "IR_GOLD_MELTED"):
        return fair_gold_18k(xau_usd, usd_irt)
    if symbol in ("IR_GOLD_24K", "IR_GOLD_1G"):
        return fair_gold_24k(xau_usd, usd_irt)
    if symbol in COIN_WEIGHTS:
        return fair_coin(symbol, xau_usd, usd_irt)
    raise ValueError(f"unknown symbol: {symbol}")


def fair_gram_weight(symbol: str) -> float:
    """وزن طلای خالص (برای implied USD)."""
    if symbol in ("IR_GOLD_18K", "IR_GOLD_MELTED"):
        return 1.0 * (GOLD_PURITY_18K / GOLD_PURITY_24K)
    if symbol in ("IR_GOLD_24K", "IR_GOLD_1G"):
        return 1.0
    if symbol in COIN_WEIGHTS:
        return COIN_WEIGHTS[symbol] * (GOLD_PURITY_COIN / GOLD_PURITY_24K)
    raise ValueError(symbol)
