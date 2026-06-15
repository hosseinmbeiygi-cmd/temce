from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class SQLMapping:
    def __init__(self, table_name: str = "historical_data") -> None:
        self.table_name = table_name
        self.field_map: dict[str, str] = {
            "symbol": "symbol",
            "date": "trade_date",
            "open": "open_price",
            "high": "high_price",
            "low": "low_price",
            "close": "close_price",
            "volume": "volume",
            "value": "trade_value",
            "count": "trade_count",
            "last": "last_price",
            "yesterday": "yesterday_close",
        }

    def to_db(self, data: dict[str, Any]) -> dict[str, Any]:
        return {self.field_map.get(k, k): v for k, v in data.items()}

    def from_db(self, row: dict[str, Any]) -> dict[str, Any]:
        reverse = {v: k for k, v in self.field_map.items()}
        return {reverse.get(k, k): v for k, v in row.items()}

    def create_table_sql(self) -> str:
        cols = ", ".join(f"{col} {self._sql_type(col)}" for col in self.field_map.values())
        return f"CREATE TABLE IF NOT EXISTS {self.table_name} (id INTEGER PRIMARY KEY AUTOINCREMENT, {cols})"

    def _sql_type(self, col: str) -> str:
        if col in ("volume", "trade_count", "trade_value"):
            return "BIGINT"
        if col in ("open_price", "high_price", "low_price", "close_price", "last_price", "yesterday_close"):
            return "REAL"
        if col == "trade_date":
            return "DATE"
        return "TEXT"
