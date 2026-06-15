from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from domain.common.value_object import ValueObject


@dataclass(frozen=True)
class Money(ValueObject):
    amount: Decimal
    currency: str = "IRR"

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError("amount must be non-negative")

    def add(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise ValueError("currency mismatch")
        return Money(self.amount + other.amount, self.currency)

    def subtract(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise ValueError("currency mismatch")
        return Money(self.amount - other.amount, self.currency)

    def multiply(self, factor: Decimal) -> Money:
        return Money(self.amount * factor, self.currency)


@dataclass(frozen=True)
class Percentage(ValueObject):
    value: float

    def __post_init__(self) -> None:
        if self.value < -100 or self.value > 100:
            raise ValueError("percentage must be between -100 and 100")

    def of(self, amount: float) -> float:
        return amount * (self.value / 100.0)


@dataclass(frozen=True)
class Range(ValueObject):
    low: float
    high: float

    def __post_init__(self) -> None:
        if self.low > self.high:
            raise ValueError("low must be <= high")

    def contains(self, value: float) -> bool:
        return self.low <= value <= self.high

    def overlap(self, other: Range) -> bool:
        return self.low <= other.high and other.low <= self.high


@dataclass(frozen=True)
class ISIN(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value or len(self.value) != 12:
            raise ValueError("ISIN must be 12 characters")
