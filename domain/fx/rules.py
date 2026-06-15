from __future__ import annotations


def validate_fx_rate(rate: float) -> bool:
    return rate > 0


def validate_spread(spread: float) -> bool:
    return spread >= 0


def validate_currency_code(code: str) -> bool:
    return len(code) == 3 and code.isalpha() and code.isupper()


def validate_pair_symbol(symbol: str) -> bool:
    parts = symbol.split("/")
    return len(parts) == 2 and all(len(p) == 3 for p in parts)


def is_major_pair(symbol: str) -> bool:
    return symbol in {"EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "USD/CAD", "AUD/USD", "NZD/USD"}
