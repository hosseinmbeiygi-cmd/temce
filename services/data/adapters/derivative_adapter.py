"""Read-only derivative adapter (Assistant 4 source layer, phase 3).

Forwards read-only forward/option fields from the motor: price, settlement,
expiry, distance_from_spot_pct.  No price calculation, no prediction, no order
entry.  ``distance_from_spot_pct = (price - spot) / spot`` only when a spot
price is definable; otherwise null.  Division-by-zero guarded.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .base import BaseAdapter, MarketRecord

RISKS_SIMPLE = ["liquidity-low", "assignment-risk"]


class DerivativeAdapter(BaseAdapter):
    source = "derivative_readonly"

    def extract(self, raw: dict[str, Any]) -> dict[str, Any]:
        price = raw.get("price")
        spot = raw.get("spot")
        distance: float | None = None
        if price is not None and spot is not None and spot != 0:
            try:
                distance = (float(price) - float(spot)) / float(spot) * 100.0
            except (TypeError, ValueError):
                distance = None

        return {
            "symbol": raw.get("symbol"),
            "value": price,
            "unit": raw.get("unit"),
            "asOf": raw.get("asOf"),
            "source": raw.get("source"),
            "quality": raw.get("quality"),
            "settlement": raw.get("settlement"),
            "expiry": raw.get("expiry"),
            "distance_from_spot_pct": distance,
            "risks_simple": list(RISKS_SIMPLE),
        }


def derivative_normalize(raw: dict[str, Any], now: datetime | None = None) -> MarketRecord:
    return DerivativeAdapter().normalize(raw, now=now)
