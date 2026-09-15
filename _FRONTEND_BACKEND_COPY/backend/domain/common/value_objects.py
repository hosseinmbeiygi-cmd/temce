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
        value = self.value.strip().upper()
        if len(value) != 12:
            raise ValueError("ISIN must be 12 characters")
        if not value[:2].isalpha():
            raise ValueError("ISIN must start with a 2-letter country code")
        if not value.isalnum():
            raise ValueError("ISIN contains invalid characters")
        if not self._valid_luhn(value):
            raise ValueError("ISIN failed Luhn checksum validation")
        # Normalise (strip/upper) while keeping the dataclass frozen.
        object.__setattr__(self, "value", value)

    @staticmethod
    def _valid_luhn(value: str) -> bool:
        """Validate the ISO 6166 Luhn check digit of an ISIN.

        Letters are converted to their numeric position (A=10 … Z=35)
        before applying the standard Luhn (mod-10) algorithm.
        """
        digits = "".join(str(ord(ch) - ord("A") + 10) if ch.isalpha() else ch for ch in value)
        total = 0
        for i, ch in enumerate(reversed(digits)):
            n = int(ch)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n -= 9
            total += n
        return total % 10 == 0
