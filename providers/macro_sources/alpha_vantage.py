"""Alpha Vantage News & Sentiment API provider.

API: ``https://www.alphavantage.co/query?function=NEWS_SENTIMENT``
Requires ``ALPHA_VANTAGE_API_KEY`` environment variable.
Free tier: 25 requests/day.

Covers gold-related news sentiment for use in the trading signal pipeline.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from core.logging import get_logger
from core.result import Result
from providers.base.base_provider import BaseProvider
from providers.macro_sources.base import MacroSourceError

logger = get_logger(__name__)

AV_BASE_URL = "https://www.alphavantage.co/query"
DEFAULT_TIMEOUT_SECONDS: float = 15.0

# Topics relevant to gold trading
GOLD_TOPICS = "gold,economy_macro,finance,forex"
GOLD_TICKERS = "COMMODITY:GOLD"


def _get_av_key() -> str:
    return os.getenv("ALPHA_VANTAGE_API_KEY", "")


@dataclass(frozen=True)
class AVNewsItem:
    """One news article with sentiment scores from Alpha Vantage."""

    title: str
    url: str
    published_at: str      # ISO-8601 datetime string
    summary: str
    source: str
    overall_sentiment_score: float
    overall_sentiment_label: str   # "Bullish" | "Somewhat-Bullish" | "Neutral" | "Bearish" | ...
    relevance_score: float         # 0.0–1.0 relevance to the requested ticker/topic
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class AlphaVantageNewsClient:
    """Fetch news sentiment from Alpha Vantage.

    Inject ``client`` in tests to avoid real network calls.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = AV_BASE_URL,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key or _get_av_key()
        self._base_url = base_url
        self._client = client
        self._timeout_seconds = timeout_seconds

    async def fetch_gold_news(
        self,
        *,
        limit: int = 50,
        time_from: str | None = None,
        sort: str = "LATEST",
    ) -> list[AVNewsItem]:
        """Fetch gold-related news articles with sentiment scores.

        Args:
            limit: maximum articles to return (max 1000 per AV docs).
            time_from: ``YYYYMMDDTHHMM`` start datetime (AV format).
            sort: ``"LATEST"`` | ``"EARLIEST"`` | ``"RELEVANCE"``.
        """
        if not self._api_key:
            raise MacroSourceError("ALPHA_VANTAGE_API_KEY is not configured")

        params: dict[str, Any] = {
            "function": "NEWS_SENTIMENT",
            "tickers":  GOLD_TICKERS,
            "topics":   GOLD_TOPICS,
            "limit":    min(int(limit), 1000),
            "sort":     sort,
            "apikey":   self._api_key,
        }
        if time_from:
            params["time_from"] = time_from

        close_client = self._client is None
        http = self._client or httpx.AsyncClient(
            timeout=self._timeout_seconds,
            follow_redirects=True,
        )
        try:
            resp = await http.get(self._base_url, params=params)
            resp.raise_for_status()
            payload = resp.json()
        except httpx.HTTPStatusError as exc:
            raise MacroSourceError(f"AlphaVantage HTTP {exc.response.status_code}") from exc
        except Exception as exc:
            logger.warning("AlphaVantage fetch failed: %s", exc)
            return []
        finally:
            if close_client:
                await http.aclose()

        # AV returns {"Information": "..."} when rate-limited / invalid key
        if "Information" in payload:
            raise MacroSourceError(f"AlphaVantage: {payload['Information']}")
        if "Note" in payload:
            raise MacroSourceError(f"AlphaVantage: {payload['Note']}")

        raw_feed: list[dict[str, Any]] = payload.get("feed") or []
        items: list[AVNewsItem] = []
        for art in raw_feed:
            overall = art.get("overall_sentiment_score", 0.0)
            label   = art.get("overall_sentiment_label", "")

            # Pick the gold ticker's relevance score when available
            relevance = 0.0
            for ts in art.get("ticker_sentiment", []):
                if ts.get("ticker") == GOLD_TICKERS:
                    relevance = float(ts.get("relevance_score", 0.0))
                    break
            if relevance == 0.0:
                for tp in art.get("topics", []):
                    if "gold" in (tp.get("topic") or "").lower():
                        relevance = max(relevance, float(tp.get("relevance_score", 0.0)))

            items.append(AVNewsItem(
                title                   = art.get("title", ""),
                url                     = art.get("url", ""),
                published_at            = art.get("time_published", ""),
                summary                 = art.get("summary", ""),
                source                  = art.get("source", ""),
                overall_sentiment_score = float(overall),
                overall_sentiment_label = label,
                relevance_score         = relevance,
            ))
        return items


class AlphaVantageNewsProvider(BaseProvider):
    """News sentiment provider using Alpha Vantage.

    Args:
        client: injectable httpx.AsyncClient for testing.
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(name="alpha_vantage_news")
        self._av = AlphaVantageNewsClient(client=client)

    async def fetch(
        self,
        limit: int = 50,
        time_from: str | None = None,
        sort: str = "LATEST",
        **kwargs: Any,
    ) -> Result[Any]:
        """Return gold-related news articles with sentiment scores.

        Args:
            limit: max number of articles.
            time_from: ``YYYYMMDDTHHMM`` start datetime.
            sort: ``"LATEST"`` | ``"EARLIEST"`` | ``"RELEVANCE"``.
        """
        try:
            items = await self._av.fetch_gold_news(
                limit=limit,
                time_from=time_from,
                sort=sort,
            )
        except MacroSourceError as exc:
            return Result.fail(str(exc))

        if not items:
            return Result.fail("AlphaVantage returned no news items")

        data = [
            {
                "title":           i.title,
                "url":             i.url,
                "published_at":    i.published_at,
                "summary":         i.summary,
                "source":          i.source,
                "sentiment_score": i.overall_sentiment_score,
                "sentiment_label": i.overall_sentiment_label,
                "relevance_score": i.relevance_score,
            }
            for i in items
        ]
        return Result.ok(data)

    async def health(self) -> dict[str, Any]:
        try:
            items = await self._av.fetch_gold_news(limit=5)
            if items:
                return {"healthy": True, "message": f"{len(items)} articles fetched"}
        except MacroSourceError as exc:
            return {"healthy": False, "message": str(exc)}
        return {"healthy": False, "message": "AlphaVantage unavailable"}
