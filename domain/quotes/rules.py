from __future__ import annotations


class OhlcConsistencyRule:
    """Validate that high >= max(open, close) and low <= min(open, close)."""

    def validate(self, high: float, low: float, open: float, close: float) -> bool:
        return high >= max(open, close) and low <= min(open, close)


class PositiveVolumeRule:
    """Validate that volume is positive."""

    def validate(self, volume: int) -> bool:
        return volume > 0


class PriceChangeRule:
    """Validate that price change is consistent with close and yesterday prices."""

    def validate(self, close: float, yesterday: float, change: float, change_pct: float) -> bool:
        if yesterday == 0:
            return change == 0 and change_pct == 0
        expected_change = close - yesterday
        expected_change_pct = (expected_change / yesterday) * 100
        return abs(change - expected_change) < 0.01 and abs(change_pct - expected_change_pct) < 0.01


class MaxPriceChangeRule:
    """Validate that price change percentage doesn't exceed the maximum."""

    def __init__(self, max_change_pct: float = 100.0) -> None:
        self.max_change_pct = max_change_pct

    def validate(self, change_pct: float) -> bool:
        return abs(change_pct) <= self.max_change_pct


class RequiredFieldsRule:
    """Validate that required fields are not empty."""

    def validate(self, symbol: str, **kwargs) -> bool:
        return bool(symbol)


def validate_quote_price(price: float) -> bool:
    return price >= 0


def validate_quote_volume(volume: int) -> bool:
    return volume >= 0


def validate_price_range(price: float, low: float, high: float) -> bool:
    return low <= price <= high


def is_price_increased(current: float, previous: float) -> bool:
    return current > previous


def is_price_decreased(current: float, previous: float) -> bool:
    return current < previous


def calculate_change_pct(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return ((current - previous) / previous) * 100.0
