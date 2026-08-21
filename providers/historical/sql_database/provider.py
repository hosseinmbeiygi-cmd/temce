from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.base_provider import BaseProvider
from providers.historical.sql_database.connection import DatabaseConnection
from providers.historical.sql_database.mapping import SQLMapping
from providers.historical.sql_database.query_builder import QueryBuilder

logger = get_logger(__name__)


class SQLDatabaseProvider(BaseProvider):
    def __init__(self, url: str | None = None) -> None:
        super().__init__(name="sql_database")
        self.db = DatabaseConnection(url)
        self.query = QueryBuilder()
        dialect = "sqlite" if self.db.url and "sqlite" in self.db.url else "postgresql"
        self.mapping = SQLMapping(dialect=dialect)

    async def fetch(self, symbol: str | None = None, **kwargs: Any) -> Result[Any]:
        if not symbol:
            return Result.fail("symbol is required")
        start = kwargs.get("start_date")
        end = kwargs.get("end_date")
        limit = kwargs.get("limit", 1000)
        offset = kwargs.get("offset", 0)
        sql, params = self.query.select(symbol, start, end, limit, offset)
        async with self.db.session() as session:
            if session is None:
                return Result.fail("Database not available")
            try:
                result = await session.execute(sql, params)
                rows = result.fetchall()
                mapped = [self.mapping.from_db(dict(r._mapping)) for r in rows]
                return Result.ok(mapped)
            except Exception as e:
                logger.error("SQL query failed: %s", e)
                return Result.fail(str(e))

    async def save(self, symbol: str, data: list[dict[str, Any]]) -> Result[int]:
        if not data:
            return Result.fail("No data to save")
        rows = [{"symbol": symbol, **self.mapping.to_db(row)} for row in data]
        sql, params = self.query.insert_many(rows)
        async with self.db.session() as session:
            if session is None:
                return Result.fail("Database not available")
            try:
                await session.execute(self.mapping.create_table_sql())
                for param_set in params:
                    await session.execute(sql, param_set)
                await session.commit()
                logger.info("Saved %d rows for %s", len(data), symbol)
                return Result.ok(len(data))
            except Exception as e:
                await session.rollback()
                logger.error("SQL save failed: %s", e)
                return Result.fail(str(e))

    async def health(self) -> dict[str, Any]:
        try:
            async with self.db.session() as session:
                if session is None:
                    return {"healthy": False, "message": "Database not available"}
                await session.execute("SELECT 1")
                return {"healthy": True, "message": "Database connected"}
        except Exception as e:
            return {"healthy": False, "message": str(e)}
