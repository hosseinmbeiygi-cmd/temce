from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class NewsPersister:
    def __init__(self, news_repository: Any | None = None) -> None:
        self.news_repo = news_repository

    async def persist(self, data: dict[str, Any]) -> Result[Any]:
        if self.news_repo is None:
            return Result.ok(data)
        result = await self.news_repo.save(data)
        if result.success:
            logger.debug("Persisted news: %s", data.get("title", "?")[:60])
        return result

    async def persist_batch(self, records: list[dict[str, Any]]) -> Result[int]:
        if self.news_repo is None:
            return Result.ok(len(records))
        count = 0
        for record in records:
            result = await self.news_repo.save(record)
            if result.success:
                count += 1
        logger.info("Persisted %d/%d news records", count, len(records))
        return Result.ok(count)

    async def find_by_symbol(self, symbol: str, limit: int = 50) -> list[dict[str, Any]]:
        if self.news_repo is None:
            return []
        result = await self.news_repo.find_by_symbol(symbol, limit=limit)
        return result.value if result.success else []

    async def find_by_sentiment(self, sentiment: str, limit: int = 50) -> list[dict[str, Any]]:
        if self.news_repo is None:
            return []
        result = await self.news_repo.find_by_sentiment(sentiment, limit=limit)
        return result.value if result.success else []

    async def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        if self.news_repo is None:
            return []
        result = await self.news_repo.search(query, limit=limit)
        return result.value if result.success else []
