from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.news import NewsProvider
from providers.news.rss.rss_client import RSSClient
from providers.news.rss.rss_parser import RSSParser

logger = get_logger(__name__)


class RSSNewsProvider(NewsProvider):
    """Base provider for fetching and parsing RSS/Atom feeds.

    Subclasses should populate `self.feeds` with name→URL mappings.
    """

    def __init__(self, name: str = "rss_news") -> None:
        super().__init__(name=name)
        self.client = RSSClient()
        self.parser = RSSParser()
        self.feeds: dict[str, str] = {}

    async def fetch_feed(self, url: str) -> Result[list[dict[str, Any]]]:
        """Fetch and parse a single RSS/Atom feed URL."""
        result = await self.client.fetch_feed(url)
        if not result.success:
            return Result.fail(result.error or "Failed to fetch RSS feed")
        raw_xml = result.value if isinstance(result.value, str) else ""
        articles = self.parser.parse(raw_xml)
        return Result.ok(articles)

    async def parse_feed(self, url: str, limit: int = 50) -> Result[list[dict[str, Any]]]:
        """Fetch a feed and return up to `limit` parsed articles."""
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
        if not self.feeds:
            logger.warning("No RSS feeds configured for %s", self.name)
            return Result.ok([])

        # Fetch all feeds in parallel with per-feed timeout (20s)
        feed_names = list(self.feeds.keys())
        feed_urls = list(self.feeds.values())
        feed_timeout = 20  # per-feed timeout in seconds

        async def _fetch_with_timeout(feed_name: str, feed_url: str) -> tuple[str, str, Result]:
            try:
                result = await asyncio.wait_for(
                    self.parse_feed(feed_url, limit),
                    timeout=feed_timeout,
                )
                return feed_name, feed_url, result
            except TimeoutError:
                logger.warning("Feed %s (%s) timed out after %ds", feed_name, feed_url, feed_timeout)
                return feed_name, feed_url, Result.fail(f"Timeout after {feed_timeout}s")
            except Exception as e:
                logger.warning("Feed %s (%s) failed: %s", feed_name, feed_url, e)
                return feed_name, feed_url, Result.fail(str(e))

        tasks = [
            _fetch_with_timeout(name, url)
            for name, url in zip(feed_names, feed_urls)
        ]
        results = await asyncio.gather(*tasks)

        all_articles: list[dict[str, Any]] = []
        for feed_name, feed_url, result in results:
            if result.success and result.value:
                # Tag each article with its feed source key
                for article in result.value:
                    article["_source_feed"] = feed_name
                all_articles.extend(result.value)

        return Result.ok(all_articles)

    async def search_news(self, query: str, limit: int = 20, **kwargs: Any) -> Result[list[dict[str, Any]]]:
        return Result.fail("Search not supported for RSS feeds")

    async def health(self) -> dict[str, Any]:
        return {"healthy": True, "message": f"{len(self.feeds)} RSS feeds"}
