from __future__ import annotations

from math import ceil
from typing import Generic, TypeVar

from pydantic import BaseModel, Field, computed_field

T = TypeVar("T")

# Hard ceiling for any single page. Endpoints may declare tighter caps via
# ``Settings.api_max_page_size``; this constant is the absolute last-resort
# guard against accidental full-table fetches.
MAX_PAGE_SIZE = 1000


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1, description="1-indexed page number")
    page_size: int = Field(
        default=50,
        ge=1,
        le=MAX_PAGE_SIZE,
        description=f"Items per page (max {MAX_PAGE_SIZE})",
    )

    @property
    def skip(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


class PaginatedResult(BaseModel, Generic[T]):
    items: list[T] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50

    @computed_field  # type: ignore[misc]
    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 1
        return max(1, ceil(self.total / self.page_size))

    @computed_field  # type: ignore[misc]
    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @computed_field  # type: ignore[misc]
    @property
    def has_prev(self) -> bool:
        return self.page > 1


def paginate(items: list, total: int, params: PaginationParams) -> PaginatedResult:
    return PaginatedResult(items=items, total=total, page=params.page, page_size=params.page_size)
