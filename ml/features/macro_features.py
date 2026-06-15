from __future__ import annotations

from typing import Any


class MacroFeatures:
    def compute(self, macro_data: dict[str, Any]) -> dict[str, float]:
        return {
            "usd_rate": 0.0,
            "gold_price": 0.0,
            "oil_price": 0.0,
            "inflation_rate": 0.0,
            "interest_rate": 0.0,
        }
