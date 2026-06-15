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
    _shared_store: dict[str, dict[str, Any]] = {}

    def __init__(self) -> None:
        cls = type(self)
        if cls.__name__ not in self._shared_store:
            self._shared_store[cls.__name__] = {}
        self._store = self._shared_store[cls.__name__]

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
