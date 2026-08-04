"""NewsIntegration — Bridge between news system and chat engine (Level 16).

Caches news results and provides formatted responses for chat.
Uses async methods to avoid blocking the event loop.
"""

from __future__ import annotations

import time
from typing import Any

from services.chat.news_analyzer import NewsAnalyzer
from services.chat.news_fetcher import NewsFetcher


class NewsIntegration:
    """Integrate news fetching and analysis with the chat engine."""

    def __init__(self, brsapi_key: str | None = None):
        self._fetcher = NewsFetcher(brsapi_key=brsapi_key)
        self._cache: dict[str, tuple[dict[str, Any], float]] = {}
        self._cache_ttl = 300  # 5 minutes

    async def get_news_for_symbol(self, symbol: str, days_back: int = 3) -> dict[str, Any]:
        """Get analyzed news for a symbol (async)."""
        cache_key = f"{symbol}_{days_back}"
        if cache_key in self._cache:
            data, ts = self._cache[cache_key]
            if time.time() - ts < self._cache_ttl:
                return data

        news = await self._fetcher.fetch_news_for_symbol(symbol, days_back)
        analysis = NewsAnalyzer.analyze(news)
        self._cache[cache_key] = (analysis, time.time())
        return analysis

    async def get_market_news(self, days_back: int = 1) -> dict[str, Any]:
        """Get analyzed market news (async)."""
        cache_key = f"market_{days_back}"
        if cache_key in self._cache:
            data, ts = self._cache[cache_key]
            if time.time() - ts < self._cache_ttl:
                return data

        news = await self._fetcher.fetch_market_news(days_back)
        analysis = NewsAnalyzer.analyze(news)
        self._cache[cache_key] = (analysis, time.time())
        return analysis

    async def get_news_for_symbols(
        self, symbols: list[str], days_back: int = 3
    ) -> dict[str, dict[str, Any]]:
        """Get news for multiple symbols (async)."""
        result = {}
        for sym in symbols:
            result[sym] = await self.get_news_for_symbol(sym, days_back)
        return result

    async def format_news_response(
        self, symbol: str, analysis: dict[str, Any] | None = None
    ) -> str:
        """Format news response for chat output."""
        if analysis is None:
            analysis = await self.get_news_for_symbol(symbol)
        return NewsAnalyzer.format_news_response(symbol, analysis)

    async def format_market_news_response(self) -> str:
        """Format market news response for chat output."""
        analysis = await self.get_market_news()
        if not analysis.get("has_news"):
            return "📭 خبر جدیدی برای بازار در دسترس نیست."

        lines = ["📰 **آخرین اخبار بازار:**", ""]
        lines.append(analysis.get("summary", ""))

        if analysis.get("top_headlines"):
            lines.append("")
            lines.append("**تیترهای مهم:**")
            for headline in analysis["top_headlines"][:5]:
                lines.append(f"  • {headline}")

        sentiment_map = {
            "positive": "🟢 مثبت",
            "negative": "🔴 منفی",
            "neutral": "⚪ خنثی",
        }
        lines.append("")
        lines.append(f"📊 **جو کلی بازار:** {sentiment_map.get(analysis['sentiment'], 'نامشخص')}")
        lines.append(f"📊 **تعداد اخبار:** {analysis.get('total_news', 0)}")

        return "\n".join(lines)
