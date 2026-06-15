from __future__ import annotations

from dataclasses import dataclass

from domain.common.value_object import ValueObject


@dataclass(frozen=True)
class PriceRange(ValueObject):
    low: float
    high: float

    def __post_init__(self) -> None:
        if self.low < 0 or self.high < 0:
            raise ValueError("prices must be non-negative")
        if self.low > self.high:
            raise ValueError("low must be <= high")

    def contains(self, price: float) -> bool:
        return self.low <= price <= self.high

    def is_within_limit(self, price: float, limit_pct: float) -> bool:
        if price <= 0 or self.low <= 0:
            return False
        max_allowed = self.high * (1 + limit_pct / 100.0)
        min_allowed = self.low * (1 - limit_pct / 100.0)
        return min_allowed <= price <= max_allowed


@dataclass(frozen=True)
class TradingVolume(ValueObject):
    quantity: int
    value: float

    def __post_init__(self) -> None:
        if self.quantity < 0:
            raise ValueError("quantity must be non-negative")
        if self.value < 0:
            raise ValueError("value must be non-negative")

    def avg_price(self) -> float:
        return self.value / self.quantity if self.quantity > 0 else 0.0
