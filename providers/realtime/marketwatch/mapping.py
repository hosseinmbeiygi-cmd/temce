from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


MARKETWATCH_FIELD_MAP = {
    "symbol": "symbol",
    "name": "name",
    "price": "last_price",
    "change": "change",
    "change_pct": "change_percent",
    "open": "open",
    "high": "high",
    "low": "low",
    "volume": "volume",
    "close": "close",
    "previous_close": "previous_close",
    "bid": "bid",
    "ask": "ask",
}


class MarketWatchMapping:
    def __init__(self, field_map: dict[str, str] | None = None) -> None:
        self.field_map = field_map or MARKETWATCH_FIELD_MAP

    def map(self, data: dict[str, Any]) -> dict[str, Any]:
        return {self.field_map.get(k, k): v for k, v in data.items()}
