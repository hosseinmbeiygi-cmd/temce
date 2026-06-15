from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


COLUMN_MAP = {
    "date": "date",
    "persian_date": "jalali_date",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "adj_close": "adjusted_close",
    "volume": "volume",
    "value": "value",
    "count": "trade_count",
    "last": "last_price",
    "first": "first_price",
    "yesterday": "yesterday_close",
}


class FileArchiveMapping:
    def __init__(self, column_map: dict[str, str] | None = None) -> None:
        self.column_map = column_map or COLUMN_MAP

    def map(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        mapped: list[dict[str, Any]] = []
        for row in data:
            new_row: dict[str, Any] = {}
            for src_key, value in row.items():
                target_key = self.column_map.get(src_key.lower(), src_key)
                new_row[target_key] = value
            mapped.append(new_row)
        return mapped

    def reverse_map(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        reverse = {v: k for k, v in self.column_map.items()}
        mapped: list[dict[str, Any]] = []
        for row in data:
            new_row: dict[str, Any] = {}
            for src_key, value in row.items():
                target_key = reverse.get(src_key, src_key)
                new_row[target_key] = value
            mapped.append(new_row)
        return mapped
