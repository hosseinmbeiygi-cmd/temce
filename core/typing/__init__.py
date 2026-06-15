from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generic, Protocol, TypeVar

T = TypeVar("T")
E = TypeVar("E", bound=BaseException)


@dataclass(frozen=True)
class Result(Generic[T]):
    value: T | None = None
    error: str | None = None
    success: bool = True

    @classmethod
    def ok(cls, value: T) -> Result[T]:
        return cls(value=value, error=None, success=True)

    @classmethod
    def fail(cls, error: str) -> Result[T]:
        return cls(value=None, error=error, success=False)

    def unwrap(self) -> T:
        if not self.success or self.value is None:
            raise ValueError(self.error or "No value")
        return self.value

    def unwrap_or(self, default: T) -> T:
        return self.value if self.success and self.value is not None else default

    def map(self, fn: Callable[[T], Any]) -> Result[Any]:
        if self.success and self.value is not None:
            return Result.ok(fn(self.value))
        return self


@dataclass(frozen=True)
class PaginatedResult(Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1


class Entity(Protocol):
    id: str
    created_at: datetime
    updated_at: datetime | None


class Repository(Protocol[T]):
    async def get(self, id: str) -> T | None: ...
    async def save(self, entity: T) -> T: ...
    async def delete(self, id: str) -> bool: ...
    async def list(self, page: int = 1, page_size: int = 100) -> PaginatedResult[T]: ...


class UseCase(Protocol[T]):
    async def execute(self, **kwargs: Any) -> T: ...


JsonDict = dict[str, Any]
JsonList = list[Any]
JsonValue = str | int | float | bool | None | JsonDict | JsonList
