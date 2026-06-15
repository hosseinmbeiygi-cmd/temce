from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from core.result import Result
from services.analytics_service import AnalyticsService
from services.quote_service import QuoteService
from services.symbol_service import SymbolService

logger = get_logger(__name__)


class SymbolReportBuilder:
    def __init__(
        self,
        symbol_service: SymbolService | None = None,
        quote_service: QuoteService | None = None,
        analytics_service: AnalyticsService | None = None,
    ):
        self._symbol_service = symbol_service or SymbolService()
        self._quote_service = quote_service or QuoteService()
        self._analytics_service = analytics_service or AnalyticsService()

    async def build(self, symbol: str, timeframe: str = "1d") -> Result[dict[str, Any]]:
        instrument = await self._symbol_service.get_by_symbol(symbol)
        quotes = await self._quote_service.get_history(symbol, timeframe=timeframe, limit=100)
        summary = await self._analytics_service.get_symbol_summary(symbol)
        data: dict[str, Any] = {
            "title": f"Symbol Report: {symbol}",
            "report_type": "symbol",
            "generated_at": datetime.now(UTC).isoformat(),
            "symbol": symbol,
            "instrument": instrument.value if instrument.success else {},
            "recent_quotes": [self._serialize_quote(q) for q in (quotes.value if quotes.success else [])],
            "summary": summary.value if summary.success else {},
        }
        return Result.ok(data)

    def _serialize_quote(self, quote: Any) -> dict[str, Any]:
        return {
            "date": getattr(quote, "date", ""),
            "price_close": getattr(quote, "price_close", 0),
            "price_open": getattr(quote, "price_open", 0),
            "price_high": getattr(quote, "price_high", 0),
            "price_low": getattr(quote, "price_low", 0),
            "volume": getattr(quote, "volume", 0),
            "price_change_pct": getattr(quote, "price_change_pct", 0),
        }
