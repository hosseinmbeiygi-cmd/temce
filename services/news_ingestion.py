from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.ids import new_id
from core.logging import get_logger
from core.result import Result
from domain.news.news_item import NewsItem
from providers.news.domestic.rss_domestic_provider import RSSDomesticProvider
from providers.news.sentiment.classifier import SentimentClassifier
from providers.news.parser import NewsParser
from services.news_dedup import NewsDeduplicator
from services.news_filter import NewsFilter
from services.news_service import NewsService

logger = get_logger(__name__)

# Reusable news parser for symbol extraction
_news_parser = NewsParser()


# Reusable date parser (avoids creating RSSParser objects repeatedly)
_DATE_FORMATS = [
    "%a, %d %b %Y %H:%M:%S %z",
    "%a, %d %b %Y %H:%M:%S %Z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
]


def _parse_rss_date(date_str: str) -> datetime | None:
    """Parse an RSS/Atom date string to a timezone-aware datetime."""
    if not date_str:
        return None
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, OverflowError):
            continue
    return None


class NewsIngestionService:
    """Orchestrates the full news ingestion pipeline.

    Pipeline: Fetch → Deduplicate → Filter → Enrich (sentiment) → Save → Display
    """

    def __init__(
        self,
        news_service: NewsService | None = None,
        deduplicator: NewsDeduplicator | None = None,
        news_filter: NewsFilter | None = None,
        sentiment_classifier: SentimentClassifier | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        self.news_service = news_service or NewsService(session=session)
        self.deduplicator = deduplicator or NewsDeduplicator(ttl_seconds=86400.0)
        self.news_filter = news_filter or NewsFilter(min_content_length=30)
        self.sentiment = sentiment_classifier or SentimentClassifier()

    async def ingest(
        self,
        sources: list[str] | None = None,
        limit_per_source: int = 50,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        keywords: list[str] | None = None,
        symbols: list[str] | None = None,
        min_content_length: int = 30,
        save: bool = True,
        verbose: bool = True,
        skip_dedup: bool = False,
        skip_sentiment: bool = False,
        top_n: int = 15,
    ) -> dict[str, Any]:
        """Run the full ingestion pipeline.

        Args:
            sources: List of RSS feed source keys (e.g. ['mehr', 'tasnim']).
                     If None, fetches from ALL configured feeds.
            limit_per_source: Max articles per RSS feed URL.
            from_date: Filter articles published on or after this date.
            to_date: Filter articles published on or before this date.
            keywords: Filter articles containing at least one keyword.
            symbols: Filter articles mentioning specific stock symbols.
            min_content_length: Minimum total text length for article to pass.
            save: If True, save to database/memory via NewsService.
            verbose: If True, print progress and article summaries to console.

        Returns:
            Dict with stats: fetched, duplicates, filtered, saved, articles list.
        """
        stats = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "fetched": 0,
            "duplicates_removed": 0,
            "filtered_out": 0,
            "saved": 0,
            "errors": 0,
            "articles": [],
        }

        # ── Step 1: Fetch ──────────────────────────────────────────
        if verbose:
            print("\n" + "=" * 70)
            print("  📡  FETCHING NEWS FROM RSS FEEDS")
            print("=" * 70)

        provider = RSSDomesticProvider()

        if sources:
            # Filter feeds to requested sources
            provider.feeds = {
                k: v for k, v in provider.feeds.items()
                if k in sources or any(k.startswith(f"{s}_") for s in sources)
            }

        raw_articles: list[dict[str, Any]] = []
        fetch_result = await provider.fetch_news(limit=limit_per_source)
        if fetch_result.success and fetch_result.value:
            raw_articles = fetch_result.value
            # Preserve _source_feed set by the provider (feed name), only fall back to RSS source tag
            for a in raw_articles:
                if "_source_feed" not in a:
                    a["_source_feed"] = a.get("source", "unknown")
            stats["fetched"] = len(raw_articles)
            if verbose:
                print(f"  ✅ Fetched {len(raw_articles)} articles from {len(provider.feeds)} feeds")
        else:
            logger.warning("No articles fetched: %s", fetch_result.error)
            if verbose:
                print(f"  ⚠️  No articles fetched: {fetch_result.error}")

        if not raw_articles:
            stats["finished_at"] = datetime.now(timezone.utc).isoformat()
            return stats

        # ── Step 2: Tag articles with feed source ──────────────────
        # The raw_articles already have their feed source tagged as
        # _source_feed from the RSS parser's output. We preserve this.

        # ── Step 3: Deduplicate ────────────────────────────────────
        before_dedup = len(raw_articles)
        if not skip_dedup:
            if verbose:
                print(f"\n  🔄  DEDUPLICATING {len(raw_articles)} articles...")

            raw_articles = self.deduplicator.deduplicate(raw_articles)
            stats["duplicates_removed"] = before_dedup - len(raw_articles)

            if verbose:
                print(f"  ✅ {len(raw_articles)} unique articles remain ({stats['duplicates_removed']} duplicates removed)")
        else:
            stats["duplicates_removed"] = 0
            if verbose:
                print(f"\n  ⏭️   Deduplication SKIPPED")

        # ── Step 4: Filter ─────────────────────────────────────────
        if verbose:
            print(f"\n  🔍  FILTERING {len(raw_articles)} articles...")

        # Apply user-specified filters
        self.news_filter.min_content_length = min_content_length
        if from_date:
            self.news_filter.from_date = from_date
        if to_date:
            self.news_filter.to_date = to_date
        if keywords:
            self.news_filter.keywords = keywords
        if symbols:
            self.news_filter.symbols = set(symbols)

        before_filter = len(raw_articles)
        filtered = self.news_filter.filter(raw_articles)
        stats["filtered_out"] = before_filter - len(filtered)

        if verbose:
            print(f"  ✅ {len(filtered)} articles passed filters ({stats['filtered_out']} filtered out)")

        # ── Step 5: Enrich with sentiment ──────────────────────────
        enriched: list[dict[str, Any]] = []
        if not skip_sentiment:
            if verbose:
                print(f"\n  🧠  RUNNING SENTIMENT ANALYSIS...")

            for article in filtered:
                text = (article.get("description") or article.get("content") or article.get("title") or "")
                try:
                    sentiment_result = self.sentiment.classify(text)
                    article["sentiment_score"] = sentiment_result.get("compound", 0.0)
                    article["sentiment_label"] = sentiment_result.get("sentiment", "neutral")
                except Exception:
                    article["sentiment_score"] = 0.0
                    article["sentiment_label"] = "neutral"
                article["relevance_score"] = self.news_filter.score_relevance(article)
                enriched.append(article)

            if verbose:
                pos = sum(1 for a in enriched if a.get("sentiment_label") == "positive")
                neg = sum(1 for a in enriched if a.get("sentiment_label") == "negative")
                neu = sum(1 for a in enriched if a.get("sentiment_label") == "neutral")
                print(f"  ✅ Sentiment: {pos} positive, {neg} negative, {neu} neutral")
        else:
            if verbose:
                print(f"\n  ⏭️   Sentiment analysis SKIPPED")
            for article in filtered:
                article["sentiment_score"] = 0.0
                article["sentiment_label"] = "neutral"
                article["relevance_score"] = self.news_filter.score_relevance(article)
                enriched.append(article)

        # ── Step 6: Save ───────────────────────────────────────────
        if save:
            if verbose:
                print(f"\n  💾  SAVING {len(enriched)} articles...")

            saved_count = 0
            for article in enriched:
                try:
                    await self._save_article(article)
                    saved_count += 1
                except Exception as e:
                    logger.error("Failed to save article '%s': %s", article.get("title", "?"), e)
                    stats["errors"] += 1
            stats["saved"] = saved_count

            if verbose:
                print(f"  ✅ Saved {saved_count} articles ({stats['errors']} errors)")

        stats["articles"] = enriched
        stats["finished_at"] = datetime.now(timezone.utc).isoformat()
        stats["deduplicator_total_removed"] = self.deduplicator.duplicates_removed

        # ── Step 7: Display summary ────────────────────────────────
        if verbose:
            self._display_summary(stats, top_n=top_n)

        return stats

    async def _save_article(self, article: dict[str, Any]) -> None:
        """Convert article dict to NewsItem and save via NewsService.

        Checks for existing articles by URL or title before saving to avoid duplicates.
        """
        url = article.get("link") or article.get("url", "")
        title = article.get("title", "Untitled")

        # Cross-run dedup: check if article with same URL or title already exists in DB
        if url or title:
            exists = await self.news_service.repo.exists_by_url_or_title(url, title)
            if exists:
                logger.debug("Skipping duplicate article (URL or title exists): %s", title[:60])
                return

        pub_date_str = article.get("published_at") or article.get("pubDate")
        pub_date = _parse_rss_date(pub_date_str) if pub_date_str else None
        if pub_date is None:
            pub_date = datetime.now(timezone.utc)

        # Extract stock symbols from article text
        text = (article.get("title") or "") + " " + (article.get("description") or "")
        symbols = _news_parser.extract_symbols(text)

        item = NewsItem(
            id=new_id("news"),
            title=article.get("title", "Untitled"),
            content=article.get("description") or article.get("content", ""),
            summary=(article.get("description") or "")[:500],
            source=article.get("_source_feed") or article.get("source", "rss"),
            url=url,
            publish_date=pub_date,
            category=article.get("category", ""),
            sentiment=article.get("sentiment_score", 0.0),
            sentiment_label=article.get("sentiment_label", "neutral"),
            symbols=symbols,
            data_source="rss",
            extra=article,
        )

        await self.news_service.save(item)

    def _display_summary(self, stats: dict[str, Any], top_n: int = 15) -> None:
        """Print a formatted summary of the ingestion results."""
        print("\n" + "=" * 70)
        print("  📊  INGESTION SUMMARY")
        print("=" * 70)
        print(f"  Fetched:           {stats['fetched']:>6,d}")
        print(f"  Duplicates removed:{stats['duplicates_removed']:>6,d}")
        print(f"  Filtered out:      {stats['filtered_out']:>6,d}")
        print(f"  Saved to DB:       {stats['saved']:>6,d}")
        print(f"  Errors:            {stats['errors']:>6,d}")
        print("-" * 70)

        articles = stats.get("articles", [])
        if articles:
            # Show top articles by relevance
            sorted_articles = sorted(articles, key=lambda a: a.get("relevance_score", 0), reverse=True)
            print(f"\n  🏆  TOP {min(top_n, len(sorted_articles))} ARTICLES (by relevance):\n")
            for i, a in enumerate(sorted_articles[:top_n], 1):
                title = (a.get("title") or "Untitled")[:75]
                source = (a.get("_source_feed") or a.get("source", "?"))[:20]
                score = a.get("relevance_score", 0)
                sent = a.get("sentiment_label", "?")[:3].upper() if a.get("sentiment_label") else "NEU"
                sent_icon = {"POS": "[+] ", "NEG": "[-] ", "NEU": "[~] "}.get(sent, "[~] ")
                print(f"  {i:>2}. {sent_icon}[{score:.2f}] [{source}] {title}")

            # Show source distribution
            print(f"\n  📡  SOURCE DISTRIBUTION:")
            source_counts: dict[str, int] = {}
            for a in articles:
                src = (a.get("_source_feed") or a.get("source", "unknown"))
                source_counts[src] = source_counts.get(src, 0) + 1
            for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
                bar = "█" * min(30, count)
                print(f"  {src:<25} {count:>4d} {bar}")

        print("=" * 70)
