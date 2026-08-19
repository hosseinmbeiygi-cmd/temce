from __future__ import annotations

from datetime import UTC, datetime, timedelta
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
        if not instrument.success:
            return Result.ok(
                {
                    "title": f"Symbol Report: {symbol}",
                    "report_type": "symbol",
                    "generated_at": datetime.now(UTC).isoformat(),
                    "symbol": symbol,
                    "instrument": {},
                    "recent_quotes": [],
                    "summary": {},
                    "notice": f"نماد {symbol} در پایگاه داده پیدا نشد.",
                }
            )

        instrument_data = instrument.value or {}
        instrument_id = instrument_data.get("id") or instrument_data.get("instrument_id") or symbol

        # Quotes: last 180 days ending today
        end_date = datetime.now(UTC).date()
        start_date = end_date - timedelta(days=180)
        quotes = await self._quote_service.get_history(
            instrument_id,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
        )

        quote_rows = quotes.value if quotes.success else []
        summary: dict[str, Any] = {}
        if quote_rows:
            closes = [q.price_close for q in quote_rows if getattr(q, "price_close", None) is not None]
            changes = [q.price_change_pct for q in quote_rows if getattr(q, "price_change_pct", None) is not None]
            if closes:
                summary["latest_close"] = closes[-1]
                summary["period_high"] = max(closes)
                summary["period_low"] = min(closes)
                summary["period_return_pct"] = ((closes[-1] / closes[0]) - 1) * 100 if closes[0] else 0
                summary["avg_volume"] = round(
                    sum(q.volume or 0 for q in quote_rows) / max(len(quote_rows), 1)
                )
            if changes:
                summary["avg_change_pct"] = round(sum(changes) / len(changes), 2)

        data: dict[str, Any] = {
            "title": f"Symbol Report: {symbol}",
            "report_type": "symbol",
            "generated_at": datetime.now(UTC).isoformat(),
            "symbol": symbol,
            "instrument": instrument_data,
            "recent_quotes": [self._serialize_quote(q) for q in quote_rows[-50:]],
            "summary": summary,
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
