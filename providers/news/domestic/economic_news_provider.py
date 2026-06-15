from __future__ import annotations

from datetime import datetime
from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.http_client import HttpClient
from providers.base.news import NewsProvider

logger = get_logger(__name__)


IRANIAN_ECONOMIC_NEWS_SOURCES = ["irna", "mehr", "tasnim", "borna", "isna"]


class EconomicNewsProvider(NewsProvider):
    def __init__(self) -> None:
        super().__init__(name="economic_news")
        self.client = HttpClient(base_url="https://api.example.com/news/domestic/economic")

    async def fetch_news(
        self,
        symbols: list[str] | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int = 50,
        **kwargs: Any,
    ) -> Result[list[dict[str, Any]]]:
        params: dict[str, Any] = {"limit": limit}
        if from_date:
            params["from"] = from_date.isoformat()
        if to_date:
            params["to"] = to_date.isoformat()
        if symbols:
            params["symbols"] = ",".join(symbols)
        result = await self.client.get("", params=params)
        if result.success:
            data = result.value.json() if hasattr(result.value, "json") else []
            return Result.ok(data if isinstance(data, list) else [])
        return Result.fail(result.error or "Unknown error")

    async def search_news(self, query: str, limit: int = 20, **kwargs: Any) -> Result[list[dict[str, Any]]]:
        result = await self.client.get("/search", params={"q": query, "limit": limit})
        if result.success:
            data = result.value.json() if hasattr(result.value, "json") else []
            return Result.ok(data if isinstance(data, list) else [])
        return Result.fail(result.error or "Unknown error")

    async def health(self) -> dict[str, Any]:
        return {"healthy": True, "message": "Economic news provider ready"}
