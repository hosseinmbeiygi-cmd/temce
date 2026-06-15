from __future__ import annotations

from dataclasses import dataclass

from domain.common.value_object import ValueObject


@dataclass(frozen=True)
class QuotePrice(ValueObject):
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    last: float = 0.0

    def __post_init__(self) -> None:
        if self.high < self.low:
            raise ValueError("high must be >= low")

    @property
    def typical_price(self) -> float:
        return (self.high + self.low + self.close) / 3.0

    @property
    def range(self) -> float:
        return self.high - self.low


@dataclass(frozen=True)
class QuoteVolume(ValueObject):
    volume: int = 0
    value: float = 0.0
    trade_count: int = 0

    def __post_init__(self) -> None:
        if self.volume < 0:
            raise ValueError("volume must be non-negative")
        if self.value < 0:
            raise ValueError("value must be non-negative")
        if self.trade_count < 0:
            raise ValueError("trade_count must be non-negative")

    @property
    def avg_trade_value(self) -> float:
        return self.value / self.trade_count if self.trade_count > 0 else 0.0

    @property
    def avg_trade_volume(self) -> float:
        return self.volume / self.trade_count if self.trade_count > 0 else 0.0
