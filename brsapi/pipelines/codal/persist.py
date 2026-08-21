from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class CodalPersister:
    def __init__(self, codal_repository: Any | None = None) -> None:
        self.codal_repo = codal_repository

    async def persist(self, data: dict[str, Any]) -> Result[Any]:
        if self.codal_repo is None:
            return Result.ok(data)
        result = await self.codal_repo.save(data)
        if result.success:
            logger.debug("Persisted codal disclosure: %s", data.get("tracking_no", "?"))
        return result

    async def persist_batch(self, records: list[dict[str, Any]]) -> Result[int]:
        if self.codal_repo is None:
            return Result.ok(len(records))
        count = 0
        for record in records:
            existing = await self.codal_repo.find_by_tracking_no(record.get("tracking_no"))
            if existing:
                logger.debug("Skipping duplicate codal: %s", record.get("tracking_no"))
                count += 1
                continue
            result = await self.codal_repo.save(record)
            if result.success:
                count += 1
        logger.info("Persisted %d/%d codal records", count, len(records))
        return Result.ok(count)

    async def find_by_instrument(self, instrument_id: str) -> list[dict[str, Any]]:
        if self.codal_repo is None:
            return []
        result = await self.codal_repo.find_by_instrument_id(instrument_id)
        return result.value if result.success else []

    async def find_by_date_range(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        if self.codal_repo is None:
            return []
        result = await self.codal_repo.find_by_date_range(start_date, end_date)
        return result.value if result.success else []
