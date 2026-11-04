from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from core.logging import get_logger
from core.result import PaginatedResult, Result

T = TypeVar("T")
logger = get_logger(__name__)


class BaseRepository(ABC, Generic[T]):
    @abstractmethod
    async def get(self, id: str) -> Result[T]: ...

    @abstractmethod
    async def save(self, entity: T) -> Result[T]: ...

    @abstractmethod
    async def delete(self, id: str) -> Result[bool]: ...

    @abstractmethod
    async def list(self, page: int = 1, page_size: int = 100) -> Result[PaginatedResult[T]]: ...

    async def exists(self, id: str) -> bool:
        result = await self.get(id)
        return result.success


class InMemoryRepository(BaseRepository[T]):
    #: Stores are shared between instances **of the same entity type**, so a
    #: repository handed out by one service is visible to another in the same
    #: process.  They must not be shared *across* entity types: keying only on
    #: the class name put instruments, quotes and every other entity into a
    #: single bucket, so a quote summary iterated ``Instrument`` rows and raised
    #: ``AttributeError: 'Instrument' object has no attribute 'instrument_id'``.
    _shared_store: dict[str, dict[str, Any]] = {}

    def __init__(self, entity_type: type | None = None) -> None:
        cls = type(self)
        key = cls.__name__ if entity_type is None else f"{cls.__name__}:{entity_type.__name__}"
        self._store = self._shared_store.setdefault(key, {})

    async def get(self, id: str) -> Result[T]:
        entity = self._store.get(id)
        if entity is None:
            return Result.fail(f"Entity {id} not found")
        return Result.ok(entity)

    async def save(self, entity: Any) -> Result[T]:
        self._store[entity.id] = entity
        return Result.ok(entity)

    async def delete(self, id: str) -> Result[bool]:
        if id in self._store:
            del self._store[id]
            return Result.ok(True)
        return Result.fail(f"Entity {id} not found")

    async def list(self, page: int = 1, page_size: int = 100) -> Result[PaginatedResult[T]]:
        items = list(self._store.values())
        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        return Result.ok(
            PaginatedResult(
                items=items[start:end],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=max(1, (total + page_size - 1) // page_size),
            )
        )

    def clear(self) -> None:
        self._store.clear()
