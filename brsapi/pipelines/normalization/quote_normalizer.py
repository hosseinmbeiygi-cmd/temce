from __future__ import annotations

from typing import Any

from core.ids import new_id


class QuoteNormalizer:
    FIELD_MAP = {
        "close": "price_close",
        "open": "price_open",
        "high": "price_high",
        "low": "price_low",
        "last": "price_last",
        "change": "price_change",
        "change_pct": "price_change_pct",
        "vol": "volume",
        "val": "value",
        "trades": "trade_count",
        "yesterday": "price_yesterday",
        "first": "price_first",
        "max": "price_max",
        "min": "price_min",
        "ask_p": "ask_price",
        "ask_v": "ask_volume",
        "bid_p": "bid_price",
        "bid_v": "bid_volume",
    }

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {"id": new_id("q")}
        for raw_key, value in raw.items():
            key = self.FIELD_MAP.get(raw_key, raw_key)
            normalized[key] = value
        if "instrument_id" not in normalized and "symbol" in normalized:
            normalized["instrument_id"] = normalized.get("symbol", "")
        return normalized
