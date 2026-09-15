from __future__ import annotations

import re
from typing import ClassVar

_SYMBOL_NORMALIZE_RE = re.compile(r"[^آ-یA-Za-z0-9_]")


def normalize_symbol(symbol: str) -> str:
    return _SYMBOL_NORMALIZE_RE.sub("", symbol.strip().upper())


def symbol_to_id(symbol: str) -> str:
    return normalize_symbol(symbol)


def symbol_from_id(symbol_id: str) -> str:
    return symbol_id


def is_valid_symbol_id(symbol_id: str) -> bool:
    return bool(symbol_id) and len(symbol_id) <= 50


class SymbolIdGenerator:
    SEPARATOR: ClassVar[str] = "_"

    @classmethod
    def to_id(cls, market: str, ticker: str) -> str:
        return f"{market.upper()}{cls.SEPARATOR}{ticker.upper()}"

    @classmethod
    def from_id(cls, symbol_id: str) -> tuple[str, str]:
        parts = symbol_id.split(cls.SEPARATOR, 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return "", symbol_id
