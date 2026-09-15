from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


MANUAL_FIELD_MAP = {
    "symbol": "symbol",
    "date": "date",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "volume": "volume",
    "value": "trade_value",
    "count": "trade_count",
    "title": "title",
    "content": "content",
    "category": "category",
    "report_type": "report_type",
    "report_date": "report_date",
}


class ManualMapping:
    def __init__(self, field_map: dict[str, str] | None = None) -> None:
        self.field_map = field_map or MANUAL_FIELD_MAP

    def map(self, data: dict[str, Any]) -> dict[str, Any]:
        return {self.field_map.get(k, k): v for k, v in data.items()}

    def reverse_map(self, data: dict[str, Any]) -> dict[str, Any]:
        reverse = {v: k for k, v in self.field_map.items()}
        return {reverse.get(k, k): v for k, v in data.items()}
