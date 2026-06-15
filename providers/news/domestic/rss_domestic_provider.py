from __future__ import annotations

from datetime import datetime
from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.news.rss.rss_provider import RSSNewsProvider

logger = get_logger(__name__)


DOMESTIC_RSS_FEEDS = {
    "irna": "https://www.irna.ir/rss",
    "mehr": "https://www.mehrnews.com/rss",
    "tasnim": "https://www.tasnimnews.com/rss",
    "borna": "https://www.borna.news/rss",
    "isna": "https://www.isna.ir/rss",
    "donya-eqtesad": "https://donya-eqtesad.com/rss",
}


class RSSDomesticProvider(RSSNewsProvider):
    def __init__(self) -> None:
        super().__init__(name="rss_domestic")
        self.feeds = DOMESTIC_RSS_FEEDS

    async def fetch_news(
        self,
        symbols: list[str] | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int = 50,
        **kwargs: Any,
    ) -> Result[list[dict[str, Any]]]:
        source = kwargs.get("source")
        if source and source in self.feeds:
            return await self.parse_feed(self.feeds[source], limit)
        all_articles: list[dict[str, Any]] = []
        for feed_url in self.feeds.values():
            result = await self.parse_feed(feed_url, limit // len(self.feeds))
            if result.success and result.value:
                all_articles.extend(result.value)
            if len(all_articles) >= limit:
                break
        return Result.ok(all_articles[:limit])

    async def search_news(self, query: str, limit: int = 20, **kwargs: Any) -> Result[list[dict[str, Any]]]:
        return Result.fail("Search not supported for RSS feeds")

    async def health(self) -> dict[str, Any]:
        return {"healthy": True, "message": f"{len(self.feeds)} RSS feeds configured"}
