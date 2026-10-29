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
        try:
            articles = self.parser.parse(raw_xml)
        except Exception as exc:  # RSSParseError or any parser failure
            # A malformed body is a failed feed, not an empty one (audit DS-03).
            logger.warning("Feed %s could not be parsed: %s", url, exc)
            return Result.fail(f"parse_error: {exc}")
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
            # A configuration gap is not a successful empty fetch: ``ok([])``
            # here made a misconfigured deployment look like a healthy ingest
            # with zero articles.
            logger.warning("No RSS feeds configured for %s", self.name)
            return Result.fail(f"no_feeds_configured:{self.name}")

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
            for name, url in zip(feed_names, feed_urls, strict=False)
        ]
        results = await asyncio.gather(*tasks)

        all_articles: list[dict[str, Any]] = []
        ok_feeds: list[str] = []
        empty_feeds: list[str] = []
        failed_feeds: list[str] = []
        for feed_name, _feed_url, result in results:
            if result.success and result.value:
                # Tag each article with its feed source key
                for article in result.value:
                    article["_source_feed"] = feed_name
                all_articles.extend(result.value)
                ok_feeds.append(feed_name)
            elif result.success:
                empty_feeds.append(feed_name)
            else:
                failed_feeds.append(f"{feed_name} ({result.error})")

        # Per-source outcome is logged even on success, so a partial outage is
        # traceable instead of hiding inside a healthy record count.
        logger.info(
            "RSS fetch %s: %d/%d feeds returned articles, %d empty, %d failed%s",
            self.name,
            len(ok_feeds),
            len(feed_names),
            len(empty_feeds),
            len(failed_feeds),
            f" — {', '.join(failed_feeds)}" if failed_feeds else "",
        )
        if failed_feeds and not ok_feeds and not empty_feeds:
            # Total failure must not be reported as a zero-record success.
            return Result.fail(f"all_feeds_failed:{self.name} — {', '.join(failed_feeds)}")
        return Result.ok(all_articles)

    async def search_news(self, query: str, limit: int = 20, **kwargs: Any) -> Result[list[dict[str, Any]]]:
        return Result.fail("Search not supported for RSS feeds")

    async def health(self) -> dict[str, Any]:
        return {"healthy": True, "message": f"{len(self.feeds)} RSS feeds"}
