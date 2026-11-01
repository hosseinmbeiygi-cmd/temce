"""Canonical Result type for the platform.

``core.typing`` re-exports this module and the legacy ``core.result`` module is
kept as a thin compatibility shim pointing here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Result(Generic[T]):
    value: T | None = None
    error: str | None = None
    success: bool = True
    # Machine-readable failure reason (e.g. ``malformed``, ``timeout``,
    # ``quota_exhausted``). Callers branch on this instead of pattern-matching
    # ``error`` text, which is prose and free to change.
    error_code: str | None = None

    @classmethod
    def ok(cls, value: T) -> Result[T]:
        return cls(value=value, error=None, success=True)

    @classmethod
    def fail(cls, error: str, code: str | None = None) -> Result[T]:
        return cls(value=None, error=error, success=False, error_code=code)

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

    def map_error(self, fn: Callable[[str], str]) -> Result[T]:
        if not self.success and self.error is not None:
            return Result.fail(fn(self.error), self.error_code)
        return self

    def and_then(self, fn: Callable[[T], Result[Any]]) -> Result[Any]:
        if self.success and self.value is not None:
            return fn(self.value)
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
