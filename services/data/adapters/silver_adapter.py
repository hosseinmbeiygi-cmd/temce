"""Silver feed adapter (Assistant 4 source layer, phase 3).

Domestic source: brsapi (toman/gram).  International fallback: spot
(USD/oz, e.g. LBMA) converted to toman/gram only when a USD/IRR reference
is supplied in the raw payload — no FX rate is invented here.  Without a
reference, the international spot is forwarded as-is with its own unit.

Output: symbol, value (toman/gram or None), unit, asOf, source, quality.
Bubble is intentionally absent — Assistant 1 owns the bubble formula.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .base import BaseAdapter, MarketRecord

# 1 troy ounce = 31.1035 grams (constant conversion, not a price).
TROY_OUNCE_GRAMS = 31.1035


class SilverAdapter(BaseAdapter):
    source = "silver_feed"

    def extract(self, raw: dict[str, Any]) -> dict[str, Any]:
        domestic = raw.get("domestic") or {}
        international = raw.get("international") or {}
        usd_irr = raw.get("usd_irr")

        domestic_val = domestic.get("value")
        intl_val = international.get("value")

        if domestic_val is not None:
            value = domestic_val
            unit = domestic.get("unit") or "toman/gram"
            source_tag = domestic.get("source") or "brsapi"
            quality = domestic.get("quality")
            as_of = domestic.get("asOf") or raw.get("asOf")
            symbol = domestic.get("symbol") or raw.get("symbol")
        elif intl_val is not None and usd_irr is not None and usd_irr != "":
            try:
                value = float(intl_val) * float(usd_irr) / TROY_OUNCE_GRAMS
            except (TypeError, ValueError):
                value = None
            unit = "toman/gram"
            source_tag = international.get("source") or "London_Bullion_Market"
            quality = international.get("quality")
            as_of = international.get("asOf") or raw.get("asOf")
            symbol = international.get("symbol") or raw.get("symbol") or "XAG_IRR"
        elif intl_val is not None:
            value = intl_val
            unit = international.get("unit")
            source_tag = international.get("source") or "London_Bullion_Market"
            quality = international.get("quality")
            as_of = international.get("asOf") or raw.get("asOf")
            symbol = international.get("symbol") or raw.get("symbol") or "XAG_IRR"
        else:
            value = None
            unit = "toman/gram"
            source_tag = "unknown"
            quality = None
            as_of = raw.get("asOf")
            symbol = raw.get("symbol") or "XAG_IRR"

        return {
            "symbol": symbol,
            "value": value,
            "unit": unit,
            "asOf": as_of,
            "source": source_tag,
            "quality": quality,
            "domestic": domestic,
            "international": international,
        }


def silver_normalize(raw: dict[str, Any], now: datetime | None = None) -> MarketRecord:
    return SilverAdapter().normalize(raw, now=now)
