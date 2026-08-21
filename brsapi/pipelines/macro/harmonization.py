from __future__ import annotations

from typing import Any

from core.ids import new_id
from core.logging import get_logger

logger = get_logger(__name__)

MACRO_FIELD_MAP = {
    "date": "date",
    "value": "value",
    "indicator": "indicator",
    "category": "category",
    "period": "period",
    "unit": "unit",
    "source": "source",
    "region": "region",
    "country": "country",
    "currency": "currency",
    "commodity": "commodity_name",
    "price": "price",
    "change": "change",
    "change_pct": "change_pct",
    "volume": "volume",
    "open": "price_open",
    "high": "price_high",
    "low": "price_low",
    "close": "price_close",
}

CATEGORY_MAP = {
    "fx": "fx",
    "ارز": "fx",
    "gold": "gold",
    "طلا": "gold",
    "commodity": "commodity",
    "کالا": "commodity",
    "energy": "energy",
    "انرژی": "energy",
    "metal": "metal",
    "فلز": "metal",
    "bond": "bond",
    "اوراق": "bond",
    "index": "index",
    "شاخص": "index",
    "interest_rate": "interest_rate",
    "نرخ بهره": "interest_rate",
    "inflation": "inflation",
    "تورم": "inflation",
    "gdp": "gdp",
    "tud": "gdp",
}


class MacroHarmonizer:
    def harmonize(self, raw: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {"id": new_id("macro")}
        for raw_key, value in raw.items():
            key = MACRO_FIELD_MAP.get(raw_key, raw_key)
            normalized[key] = value
        raw_cat = normalized.get("category", "")
        normalized["category"] = CATEGORY_MAP.get(raw_cat, raw_cat)
        if isinstance(normalized.get("value"), str):
            try:
                normalized["value"] = float(normalized["value"].replace(",", "").replace("٬", ""))
            except (ValueError, AttributeError):
                normalized["value"] = 0.0
        if isinstance(normalized.get("price"), str):
            try:
                normalized["price"] = float(normalized["price"].replace(",", "").replace("٬", ""))
            except (ValueError, AttributeError):
                normalized["price"] = 0.0
        normalized.setdefault("source", "unknown")
        normalized.setdefault("extra", {})
        logger.debug("Harmonized macro: %s = %s", normalized.get("indicator", "?"), normalized.get("value"))
        return normalized

    def harmonize_batch(self, raw_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.harmonize(raw) for raw in raw_list]
