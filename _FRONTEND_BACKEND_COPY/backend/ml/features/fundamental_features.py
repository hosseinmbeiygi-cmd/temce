from __future__ import annotations

from typing import Any


class FundamentalFeatures:
    def compute(self, data: Any) -> dict[str, float]:
        return {"pe_ratio": 0.0, "pb_ratio": 0.0, "eps": 0.0, "roe": 0.0, "debt_to_equity": 0.0}
