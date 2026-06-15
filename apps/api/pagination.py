from __future__ import annotations

from math import ceil
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = 1
    page_size: int = 50

    @property
    def skip(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


class PaginatedResult(BaseModel, Generic[T]):
    items: list[T] = []
    total: int = 0
    page: int = 1
    page_size: int = 50

    @property
    def total_pages(self) -> int:
        return max(1, ceil(self.total / self.page_size)) if self.page_size > 0 else 1

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1


def paginate(items: list, total: int, params: PaginationParams) -> PaginatedResult:
    return PaginatedResult(items=items, total=total, page=params.page, page_size=params.page_size)
