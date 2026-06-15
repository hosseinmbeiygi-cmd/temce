from __future__ import annotations

import re

from core.validation import validate_required

IR_SYMBOL_PATTERN = re.compile(r"^[آ-یA-Za-z0-9_-]+$")
ISIN_PATTERN = re.compile(r"^IR[A-Z0-9]{10}$")
TICKER_PATTERN = re.compile(r"^[A-Za-zآ-ی0-9]+$")


def validate_symbol(symbol: str) -> None:
    validate_required(symbol, "symbol")
    if not IR_SYMBOL_PATTERN.match(symbol):
        raise ValueError(f"Invalid symbol format: {symbol}")


def validate_isin(isin: str) -> None:
    validate_required(isin, "isin")
    if not ISIN_PATTERN.match(isin):
        raise ValueError(f"Invalid ISIN format: {isin}")


def validate_ticker(ticker: str) -> None:
    validate_required(ticker, "ticker")
    if not TICKER_PATTERN.match(ticker):
        raise ValueError(f"Invalid ticker format: {ticker}")


def normalize_symbol(symbol: str) -> str:
    return re.sub(r"[^آ-یA-Za-z0-9_]", "", symbol.strip().upper())


def normalize_isin(isin: str) -> str:
    return isin.strip().upper()
