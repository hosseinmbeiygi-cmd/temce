from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ConversionResult:
    from_currency: str = ""
    to_currency: str = ""
    amount: float = 0.0
    converted_amount: float = 0.0
    rate: float = 0.0
    timestamp: datetime | None = None

    @property
    def is_inverse(self) -> bool:
        return False
