from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AssetType(StrEnum):
    GOLD = "gold"
    GOLD_COIN = "gold_coin"
    GOLD_FUND = "gold_fund"
    FX = "fx"
    FX_REFERENCE_ONLY = "fx_reference_only"
    GLOBAL_REFERENCE = "global_reference"
    CRYPTO_ADJACENT = "crypto_adjacent"


@dataclass(frozen=True)
class SymbolMeta:
    canonical_id: str
    asset_type: AssetType
    display_name: str
    brsapi_symbol: str | None = None
    daily_volatility: float = 0.015
    purity: float | None = None
    daily_max_jump_pct: float = 0.08
    intraday_max_jump_pct: float = 0.05
    intraday_min_active_bars_per_day: int = 150


GOLD_WEIGHT_SYMBOLS: dict[str, SymbolMeta] = {
    "gold_1g": SymbolMeta(
        "GOLD_1G",
        AssetType.GOLD,
        "طلای یک‌گرمی",
        brsapi_symbol="IR_GOLD_1G",
        purity=1.0,
        daily_volatility=0.012,
        intraday_max_jump_pct=0.05,
    ),
    "gold_18k": SymbolMeta(
        "GOLD_18K",
        AssetType.GOLD,
        "طلای ۱۸ عیار",
        brsapi_symbol="IR_GOLD_18K",
        purity=0.75,
        daily_volatility=0.012,
        intraday_max_jump_pct=0.05,
    ),
    "gold_24k": SymbolMeta(
        "GOLD_24K",
        AssetType.GOLD,
        "طلای ۲۴ عیار",
        brsapi_symbol="IR_GOLD_24K",
        purity=1.0,
        daily_volatility=0.012,
        intraday_max_jump_pct=0.05,
    ),
}

GOLD_COIN_SYMBOLS: dict[str, SymbolMeta] = {
    "coin_emami": SymbolMeta(
        "COIN_EMAMI",
        AssetType.GOLD_COIN,
        "سکه امامی",
        brsapi_symbol="IR_COIN_EMAMI",
        daily_volatility=0.018,
        intraday_max_jump_pct=0.06,
    ),
    "coin_parsian": SymbolMeta(
        "COIN_PARSIAN",
        AssetType.GOLD_COIN,
        "سکه پارسیان",
        brsapi_symbol="IR_COIN_PARSIAN",
        daily_volatility=0.018,
        intraday_max_jump_pct=0.06,
    ),
    "coin_half": SymbolMeta(
        "COIN_HALF",
        AssetType.GOLD_COIN,
        "نیم سکه",
        brsapi_symbol="IR_COIN_HALF",
        daily_volatility=0.020,
        intraday_max_jump_pct=0.07,
    ),
    "coin_quarter": SymbolMeta(
        "COIN_QUARTER",
        AssetType.GOLD_COIN,
        "ربع سکه",
        brsapi_symbol="IR_COIN_QUARTER",
        daily_volatility=0.022,
        intraday_max_jump_pct=0.08,
    ),
    "coin_gerami": SymbolMeta(
        "COIN_GERAMI",
        AssetType.GOLD_COIN,
        "سکه گرمی",
        brsapi_symbol="IR_COIN_GERAMI",
        daily_volatility=0.025,
        intraday_max_jump_pct=0.09,
    ),
}

GOLD_FUND_SYMBOLS: dict[str, SymbolMeta] = {
    "gold_fund_ime": SymbolMeta(
        "GOLD_FUND_IME", AssetType.GOLD_FUND, "صندوق طلا / بورس کالا", brsapi_symbol=None, daily_volatility=0.015
    ),
}

GLOBAL_REFERENCE_SYMBOLS: dict[str, SymbolMeta] = {
    "xau_usd": SymbolMeta(
        "XAU_USD", AssetType.GLOBAL_REFERENCE, "اونس جهانی طلا", brsapi_symbol="XAUUSD", daily_volatility=0.015
    ),
}

_FX_SAMPLE_CODES: list[tuple[str, str, float, float]] = [
    ("USD", "دلار آمریکا", 0.08, 0.018),
    ("EUR", "یورو", 0.08, 0.018),
    ("GBP", "پوند انگلیس", 0.08, 0.018),
    ("AED", "درهم امارات", 0.06, 0.014),
    ("SAR", "ریال عربستان", 0.06, 0.014),
    ("TRY", "لیر ترکیه", 0.10, 0.024),
    ("CNY", "یوان چین", 0.06, 0.014),
    ("JPY", "ین ژاپن", 0.07, 0.016),
    ("CHF", "فرانک سوئیس", 0.07, 0.016),
    ("CAD", "دلار کانادا", 0.07, 0.016),
    ("AUD", "دلار استرالیا", 0.07, 0.017),
    ("KWD", "دینار کویت", 0.06, 0.014),
    ("IQD", "دینار عراق", 0.09, 0.020),
    ("INR", "روپیه هند", 0.07, 0.017),
    ("RUB", "روبل روسیه", 0.10, 0.026),
    ("AFN", "افغانی", 0.09, 0.020),
]

FX_SYMBOLS: dict[str, SymbolMeta] = {
    f"{code.lower()}_irr_free": SymbolMeta(
        f"{code}_IRR_FREE",
        AssetType.FX,
        f"{name} / بازار آزاد",
        brsapi_symbol=code,
        daily_volatility=vol,
        daily_max_jump_pct=jump,
        intraday_max_jump_pct=jump * 0.7,
    )
    for code, name, jump, vol in _FX_SAMPLE_CODES
}

FX_REFERENCE_SYMBOLS: dict[str, SymbolMeta] = {
    "usd_irr_nima": SymbolMeta(
        "USD_IRR_NIMA", AssetType.FX_REFERENCE_ONLY, "دلار / نیمایی (مرجع)", brsapi_symbol=None, daily_volatility=0.010
    ),
}

CRYPTO_ADJACENT_SYMBOLS: dict[str, SymbolMeta] = {
    "usdt_irt": SymbolMeta(
        "USDT_IRT", AssetType.CRYPTO_ADJACENT, "تتر", brsapi_symbol="USDT_IRT", daily_volatility=0.020
    ),
}

SYMBOL_REGISTRY: dict[str, SymbolMeta] = {
    **GOLD_WEIGHT_SYMBOLS,
    **GOLD_COIN_SYMBOLS,
    **GOLD_FUND_SYMBOLS,
    **GLOBAL_REFERENCE_SYMBOLS,
    **FX_SYMBOLS,
    **FX_REFERENCE_SYMBOLS,
    **CRYPTO_ADJACENT_SYMBOLS,
}

DEFAULT_VOLATILITY = 0.015


def get_symbol_meta(symbol: str) -> SymbolMeta:
    meta = SYMBOL_REGISTRY.get(symbol)
    if meta is None:
        return SymbolMeta(symbol.upper(), AssetType.FX, symbol, daily_volatility=DEFAULT_VOLATILITY)
    return meta


def is_fair_value_applicable(symbol: str) -> bool:
    return get_symbol_meta(symbol).asset_type == AssetType.GOLD


def symbols_by_type(asset_type: AssetType) -> list[str]:
    return [k for k, v in SYMBOL_REGISTRY.items() if v.asset_type == asset_type]


def brsapi_to_canonical_map(*asset_types: AssetType) -> dict[str, str]:
    return {v.brsapi_symbol: k for k, v in SYMBOL_REGISTRY.items() if v.asset_type in asset_types and v.brsapi_symbol}


def all_intraday_eligible_symbols() -> list[str]:
    eligible_types = {AssetType.GOLD, AssetType.GOLD_COIN, AssetType.GOLD_FUND, AssetType.FX}
    return [k for k, v in SYMBOL_REGISTRY.items() if v.asset_type in eligible_types]
