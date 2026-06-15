from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


TSETMC_FIELD_MAP = {
    "insCode": "instrument_code",
    "symbol": "symbol",
    "name": "name",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "last": "last_price",
    "volume": "volume",
    "value": "trade_value",
    "count": "trade_count",
    "yesterday": "yesterday_close",
    "first": "first_price",
    "max": "daily_max",
    "min": "daily_min",
    "eps": "eps",
    "pe": "pe_ratio",
    "bid_price": "bid_price",
    "bid_volume": "bid_volume",
    "ask_price": "ask_price",
    "ask_volume": "ask_volume",
}


class TsetmcMapping:
    def __init__(self, field_map: dict[str, str] | None = None) -> None:
        self.field_map = field_map or TSETMC_FIELD_MAP

    def map_quote(self, data: dict[str, Any]) -> dict[str, Any]:
        return {self.field_map.get(k, k): v for k, v in data.items()}

    def map_orderbook(self, data: dict[str, Any]) -> dict[str, Any]:
        return {
            "buy_rows": [
                {"price": r.get("price"), "volume": r.get("volume"), "count": r.get("count")}
                for r in data.get("buy_rows", [])
            ],
            "sell_rows": [
                {"price": r.get("price"), "volume": r.get("volume"), "count": r.get("count")}
                for r in data.get("sell_rows", [])
            ],
        }
