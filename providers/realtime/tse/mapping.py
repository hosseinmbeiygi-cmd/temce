from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


TSE_REALTIME_FIELD_MAP = {
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
    "index_total": "total_index",
    "index_float": "float_index",
}


class TseRealtimeMapping:
    def __init__(self, field_map: dict[str, str] | None = None) -> None:
        self.field_map = field_map or TSE_REALTIME_FIELD_MAP

    def map(self, data: dict[str, Any]) -> dict[str, Any]:
        return {self.field_map.get(k, k): v for k, v in data.items()}

    def map_batch(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.map(row) for row in data]
