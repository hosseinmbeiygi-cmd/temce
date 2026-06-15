from __future__ import annotations

from datetime import datetime
from typing import Any


class QueryBuilder:
    def __init__(self, table: str = "historical_data") -> None:
        self.table = table

    def insert(self, data: dict[str, Any]) -> tuple[str, list[Any]]:
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        sql = f"INSERT INTO {self.table} ({cols}) VALUES ({placeholders})"
        return sql, list(data.values())

    def insert_many(self, rows: list[dict[str, Any]]) -> tuple[str, list[list[Any]]]:
        if not rows:
            return "", []
        cols = ", ".join(rows[0].keys())
        placeholders = ", ".join("?" for _ in rows[0])
        sql = f"INSERT INTO {self.table} ({cols}) VALUES ({placeholders})"
        params = [list(r.values()) for r in rows]
        return sql, params

    def select(
        self,
        symbol: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> tuple[str, list[Any]]:
        conditions: list[str] = []
        params: list[Any] = []
        if symbol:
            conditions.append("symbol = ?")
            params.append(symbol)
        if start_date:
            conditions.append("trade_date >= ?")
            params.append(start_date.date())
        if end_date:
            conditions.append("trade_date <= ?")
            params.append(end_date.date())
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"SELECT * FROM {self.table}{where} ORDER BY trade_date DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        return sql, params

    def count(self, symbol: str | None = None) -> tuple[str, list[Any]]:
        if symbol:
            return f"SELECT COUNT(*) FROM {self.table} WHERE symbol = ?", [symbol]
        return f"SELECT COUNT(*) FROM {self.table}", []

    def delete(self, symbol: str, before: datetime | None = None) -> tuple[str, list[Any]]:
        if before:
            return f"DELETE FROM {self.table} WHERE symbol = ? AND trade_date < ?", [symbol, before.date()]
        return f"DELETE FROM {self.table} WHERE symbol = ?", [symbol]
