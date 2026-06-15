from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass
class ProviderResult(Generic[T]):
    success: bool = True
    data: T | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def ok(cls, data: T, **metadata: Any) -> ProviderResult[T]:
        return cls(success=True, data=data, metadata=metadata)

    @classmethod
    def fail(cls, error: str, **metadata: Any) -> ProviderResult[T]:
        return cls(success=False, error=error, metadata=metadata)
