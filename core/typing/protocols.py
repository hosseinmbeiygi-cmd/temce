from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, TypeVar, runtime_checkable

T = TypeVar("T", bound="Entity")


@runtime_checkable
class Entity(Protocol):
    id: str
    created_at: datetime
    updated_at: datetime | None


@runtime_checkable
class Repository(Protocol[T]):
    async def get(self, id: str) -> T | None: ...
    async def save(self, entity: T) -> T: ...
    async def delete(self, id: str) -> bool: ...
    async def list(self, page: int = 1, page_size: int = 100) -> Any: ...


@runtime_checkable
class UseCase(Protocol[T]):
    async def execute(self, **kwargs: Any) -> T: ...


@runtime_checkable
class Serializer(Protocol[T]):
    def serialize(self, obj: T) -> str: ...
    def deserialize(self, data: str) -> T: ...


@runtime_checkable
class HasID(Protocol):
    id: str
