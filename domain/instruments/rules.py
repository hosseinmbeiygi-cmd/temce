from __future__ import annotations

from domain.common.enum_types import InstrumentStatus
from domain.instruments.enums import BoardType


class SymbolRequiredRule:
    """Validate that a symbol is non-empty and valid."""

    def validate(self, symbol: str) -> bool:
        return bool(symbol) and len(symbol) <= 20 and symbol.isalnum()


class IsinFormatRule:
    """Validate that an ISIN has the correct format (12 alphanumeric chars)."""

    def validate(self, isin: str) -> bool:
        return len(isin) == 12 and isin.isalnum()


class MarketTypeRule:
    """Validate that market type is in the allowed list."""

    def __init__(self, allowed_types: list[str] | None = None) -> None:
        self.allowed_types = allowed_types or []

    def validate(self, market_type: str) -> bool:
        return market_type in self.allowed_types


class ParValueRule:
    """Validate that par value is positive."""

    def validate(self, par_value: float) -> bool:
        return par_value > 0


class UniqueSymbolRule:
    """Validate that a symbol is not already taken."""

    def __init__(self, existing_symbols: list[str] | None = None) -> None:
        self.existing_symbols = existing_symbols or []

    def validate(self, symbol: str) -> bool:
        return symbol not in self.existing_symbols


def can_trade_instrument(status: InstrumentStatus, is_market_open: bool) -> bool:
    return status == InstrumentStatus.ACTIVE and is_market_open


def validate_symbol(symbol: str) -> bool:
    return bool(symbol) and len(symbol) <= 20 and symbol.isalnum()


def validate_isin(isin: str) -> bool:
    return len(isin) == 12 and isin.isalnum()


def validate_tick_size(price: float, tick_size: float) -> bool:
    if tick_size <= 0:
        return False
    return price % tick_size == 0


def validate_board_type(board_type: str) -> bool:
    return board_type in {b.value for b in BoardType}
