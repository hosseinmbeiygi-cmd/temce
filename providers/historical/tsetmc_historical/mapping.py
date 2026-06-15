from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


TSETMC_HISTORICAL_FIELDS = {
    "insCode": "instrument_code",
    "date": "date",
    "jalaliDate": "jalali_date",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "last": "last_price",
    "volume": "volume",
    "value": "trade_value",
    "count": "trade_count",
    "yesterdayClose": "yesterday_close",
    "first": "first_price",
    "max": "daily_max",
    "min": "daily_min",
}


class TsetmcHistoricalMapping:
    def __init__(self, field_map: dict[str, str] | None = None) -> None:
        self.field_map = field_map or TSETMC_HISTORICAL_FIELDS

    def map_row(self, row: dict[str, Any]) -> dict[str, Any]:
        mapped: dict[str, Any] = {}
        for src_key, value in row.items():
            target_key = self.field_map.get(src_key, src_key)
            mapped[target_key] = value
        return mapped

    def map_batch(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.map_row(r) for r in rows]

    def reverse(self, row: dict[str, Any]) -> dict[str, Any]:
        reverse_map = {v: k for k, v in self.field_map.items()}
        return {reverse_map.get(k, k): v for k, v in row.items()}
