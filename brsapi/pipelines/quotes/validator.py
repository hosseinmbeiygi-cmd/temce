from __future__ import annotations

import re
from typing import Any


class QuoteValidator:
    """Validator for quote data."""

    REQUIRED_FIELDS = {"symbol", "price_close", "volume", "date"}

    def validate(self, quote: dict[str, Any]) -> bool:
        for field in self.REQUIRED_FIELDS:
            if field not in quote or quote[field] is None or quote[field] == "":
                return False
        return True

    def validate_field(self, field_name: str, value: Any) -> bool:
        if field_name == "price_close":
            return isinstance(value, (int, float)) and value >= 0
        elif field_name == "date":
            if isinstance(value, str):
                return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", value))
            return False
        return True

    def validate_ohlc(self, high: float, low: float, open: float, close: float) -> bool:
        return high >= max(open, close) and low <= min(open, close)
