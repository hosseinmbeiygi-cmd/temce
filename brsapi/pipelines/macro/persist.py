from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class MacroPersister:
    def __init__(self, macro_repository: Any | None = None) -> None:
        self.macro_repo = macro_repository

    async def persist(self, data: dict[str, Any]) -> Result[Any]:
        if self.macro_repo is None:
            return Result.ok(data)
        result = await self.macro_repo.save(data)
        if result.success:
            logger.debug("Persisted macro: %s", data.get("indicator", "?"))
        return result

    async def persist_batch(self, records: list[dict[str, Any]]) -> Result[int]:
        if self.macro_repo is None:
            return Result.ok(len(records))
        count = 0
        for record in records:
            result = await self.macro_repo.save(record)
            if result.success:
                count += 1
        logger.info("Persisted %d/%d macro records", count, len(records))
        return Result.ok(count)

    async def find_by_category(self, category: str, limit: int = 100) -> list[dict[str, Any]]:
        if self.macro_repo is None:
            return []
        result = await self.macro_repo.find_by_category(category, limit=limit)
        return result.value if result.success else []

    async def find_by_indicator(self, indicator: str, limit: int = 100) -> list[dict[str, Any]]:
        if self.macro_repo is None:
            return []
        result = await self.macro_repo.find_by_indicator(indicator, limit=limit)
        return result.value if result.success else []

    async def get_latest(self, indicator: str) -> dict[str, Any] | None:
        if self.macro_repo is None:
            return None
        result = await self.macro_repo.get_latest(indicator)
        return result.value if result.success else None
