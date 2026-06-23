from __future__ import annotations

import math
from typing import Generic, TypeVar

T = TypeVar("T")


class PageParams:
    def __init__(self, page: int = 1, page_size: int = 50) -> None:
        self.page = max(1, page)
        self.page_size = min(max(1, page_size), 1000)

    @property
    def skip(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


class Page(Generic[T]):
    def __init__(self, items: list[T], total: int, page: int, page_size: int) -> None:
        super().__init__()
        self.items = items
        self.total = total
        self.page = page
        self.page_size = page_size

    @property
    def total_pages(self) -> int:
        return max(1, math.ceil(self.total / self.page_size)) if self.page_size > 0 else 1

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    def to_dict(self) -> dict:
        return {
            "items": self.items,
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
            "total_pages": self.total_pages,
        }
