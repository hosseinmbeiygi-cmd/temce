from __future__ import annotations

from abc import abstractmethod
from datetime import datetime
from typing import Any

from core.result import Result
from providers.base.base_provider import BaseProvider


class NewsProvider(BaseProvider):
    @abstractmethod
    async def fetch_news(
        self,
        symbols: list[str] | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int = 50,
        **kwargs: Any,
    ) -> Result[list[dict[str, Any]]]: ...

    @abstractmethod
    async def search_news(self, query: str, limit: int = 20, **kwargs: Any) -> Result[list[dict[str, Any]]]: ...
