from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SourcePayload(BaseModel):
    source: str
    endpoint: str
    raw_data: bytes
    content_type: str
    fetch_time: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class FetchResult(BaseModel):
    payloads: list[SourcePayload]
    cursor: str | None = None
    has_more: bool = False


class DataSource(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    async def fetch(self, context: dict[str, Any] | None = None) -> FetchResult:
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        ...

    async def close(self) -> None:
        ...
