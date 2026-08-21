from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class BasePersister(ABC):
    """Base class for all pipeline persisters.

    Persisters write validated/enriched records to storage repositories
    with idempotent upsert semantics.
    """

    def __init__(self, name: str | None = None) -> None:
        self.name = name or self.__class__.__name__

    @abstractmethod
    async def persist(self, record: dict[str, Any]) -> Result[Any]:
        """Persist a single record. Returns Result with persisted entity."""
        ...

    async def persist_batch(self, records: list[dict[str, Any]]) -> Result[int]:
        """Persist a batch of records. Returns count of successfully persisted."""
        count = 0
        for record in records:
            result = await self.persist(record)
            if result.success:
                count += 1
            else:
                logger.error("Persist failed in %s: %s", self.name, result.error)
        logger.info("Persisted %d/%d records in %s", count, len(records), self.name)
        return Result.ok(count)

    async def upsert(self, record: dict[str, Any], key_fields: list[str]) -> Result[Any]:
        """Upsert a record by checking key_fields for existing match."""
        existing = await self.find_existing(record, key_fields)
        if existing:
            return await self.update(existing["id"], record)
        return await self.persist(record)

    @abstractmethod
    async def find_existing(self, record: dict[str, Any], key_fields: list[str]) -> dict[str, Any] | None:
        """Find existing record matching key fields."""
        ...

    @abstractmethod
    async def update(self, record_id: str, record: dict[str, Any]) -> Result[Any]:
        """Update an existing record."""
        ...
