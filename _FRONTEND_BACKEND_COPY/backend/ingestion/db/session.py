from __future__ import annotations

from typing import Any

import asyncpg
from pydantic import PostgresDsn


class DatabaseSession:
    def __init__(self, dsn: PostgresDsn) -> None:
        self._dsn = str(dsn)
        self._pool: asyncpg.Pool | None = None

    async def start(self, pool_size: int = 10, max_overflow: int = 20) -> None:
        self._pool = await asyncpg.create_pool(
            self._dsn,
            min_size=pool_size // 2,
            max_size=pool_size + max_overflow,
        )

    async def stop(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("DatabaseSession not started")
        return self._pool

    async def acquire(self) -> asyncpg.Connection:
        return await self.pool.acquire()

    async def release(self, conn: asyncpg.Connection) -> None:
        await self.pool.release(conn)

    async def fetchrow(self, query: str, *args: Any) -> Any:
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def execute(self, query: str, *args: Any) -> str:
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)
