from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


TSE_ARCHIVE_FIELD_MAP = {
    "ticker": "ticker_id",
    "date": "persian_date",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "volume": "volume",
    "value": "trade_value",
    "count": "trade_count",
    "last": "last_price",
    "yesterday": "yesterday_close",
    "first": "first_price",
}


class TseArchiveMapping:
    def __init__(self, field_map: dict[str, str] | None = None) -> None:
        self.field_map = field_map or TSE_ARCHIVE_FIELD_MAP

    def map_row(self, row: dict[str, Any]) -> dict[str, Any]:
        return {self.field_map.get(k, k): v for k, v in row.items()}

    def map_batch(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.map_row(r) for r in rows]

    def reverse_map(self, row: dict[str, Any]) -> dict[str, Any]:
        reverse = {v: k for k, v in self.field_map.items()}
        return {reverse.get(k, k): v for k, v in row.items()}
