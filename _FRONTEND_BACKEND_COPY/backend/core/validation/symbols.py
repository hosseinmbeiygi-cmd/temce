"""Symbol / ISIN validation and normalization.

The canonical ``validate_symbol`` / ``validate_isin`` live in
``core.validation`` (package root).  This module re-exports them and adds
ticker-specific helpers.
"""

from __future__ import annotations

import re

from core.validation import (  # noqa: F401 — re-exported for backward compat
    IR_SYMBOL_PATTERN,
    ISIN_PATTERN,
    validate_isin,
    validate_required,
    validate_symbol,
)

TICKER_PATTERN = re.compile(r"^[A-Za-zآ-ی0-9]+$")


def validate_ticker(ticker: str) -> None:
    validate_required(ticker, "ticker")
    if not TICKER_PATTERN.match(ticker):
        raise ValueError(f"Invalid ticker format: {ticker}")


def normalize_symbol(symbol: str) -> str:
    return re.sub(r"[^آ-یA-Za-z0-9_]", "", symbol.strip().upper())


def normalize_isin(isin: str) -> str:
    return isin.strip().upper()


__all__ = [
    "validate_symbol",
    "validate_isin",
    "validate_ticker",
    "normalize_symbol",
    "normalize_isin",
    "IR_SYMBOL_PATTERN",
    "ISIN_PATTERN",
    "TICKER_PATTERN",
]
