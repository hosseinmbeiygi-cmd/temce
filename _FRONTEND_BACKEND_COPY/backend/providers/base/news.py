from __future__ import annotations

from abc import abstractmethod
from datetime import datetime
from typing import Any

from core.result import Result
from providers.base.base_provider import BaseProvider


class NewsProvider(BaseProvider):
    """Abstract base class for all news providers.

    Subclasses must implement `fetch_news` and `search_news`.
    The `fetch` method (required by BaseProvider) delegates to `fetch_news`.
    """

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

    async def fetch(self, **kwargs: Any) -> Result[Any]:
        """Delegate to fetch_news so BaseProvider's retry/circuit-breaker works."""
        return await self.fetch_news(**kwargs)
