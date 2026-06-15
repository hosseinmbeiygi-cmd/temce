from __future__ import annotations

from datetime import datetime
from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.news import NewsProvider
from providers.news.rss.rss_client import RSSClient
from providers.news.rss.rss_parser import RSSParser

logger = get_logger(__name__)


class RSSNewsProvider(NewsProvider):
    def __init__(self, name: str = "rss_news") -> None:
        super().__init__(name=name)
        self.client = RSSClient()
        self.parser = RSSParser()
        self.feeds: dict[str, str] = {}

    async def fetch_feed(self, url: str) -> Result[list[dict[str, Any]]]:
        result = await self.client.fetch_feed(url)
        if not result.success:
            return Result.fail(result.error or "Failed to fetch RSS feed")
        raw_xml = result.value if isinstance(result.value, str) else ""
        articles = self.parser.parse(raw_xml)
        return Result.ok(articles)

    async def parse_feed(self, url: str, limit: int = 50) -> Result[list[dict[str, Any]]]:
        result = await self.fetch_feed(url)
        if result.success and result.value:
            return Result.ok(result.value[:limit])
        return result

    async def fetch_news(
        self,
        symbols: list[str] | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int = 50,
        **kwargs: Any,
    ) -> Result[list[dict[str, Any]]]:
        all_articles: list[dict[str, Any]] = []
        for _feed_name, feed_url in self.feeds.items():
            result = await self.parse_feed(feed_url, limit)
            if result.success and result.value:
                all_articles.extend(result.value)
                if len(all_articles) >= limit:
                    break
        return Result.ok(all_articles[:limit])

    async def search_news(self, query: str, limit: int = 20, **kwargs: Any) -> Result[list[dict[str, Any]]]:
        return Result.fail("Search not supported for RSS feeds")

    async def health(self) -> dict[str, Any]:
        return {"healthy": True, "message": f"{len(self.feeds)} RSS feeds"}
