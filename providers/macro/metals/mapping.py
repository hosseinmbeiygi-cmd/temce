from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


METAL_FIELD_MAP = {
    "name": "name",
    "symbol": "symbol",
    "price": "price",
    "change": "change",
    "change_pct": "change_percent",
    "bid": "bid",
    "ask": "ask",
    "high": "high",
    "low": "low",
    "open": "open",
    "close": "close",
    "volume": "volume",
    "date": "date",
    "unit": "unit",
    "exchange": "exchange",
}


class MetalsMapping:
    def __init__(self, field_map: dict[str, str] | None = None) -> None:
        self.field_map = field_map or METAL_FIELD_MAP

    def map(self, data: dict[str, Any]) -> dict[str, Any]:
        return {self.field_map.get(k, k): v for k, v in data.items()}

    def map_batch(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.map(row) for row in data]
