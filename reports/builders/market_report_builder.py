from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from core.result import Result
from services.market_service import MarketService

logger = get_logger(__name__)


class MarketReportBuilder:
    def __init__(self, market_service: MarketService | None = None):
        self._service = market_service or MarketService()

    async def build(self, date: str | None = None) -> Result[dict[str, Any]]:
        overview = await self._service.get_overview()
        gainers = await self._service.get_top_gainers(10)
        losers = await self._service.get_top_losers(10)
        active = await self._service.get_most_active(10)
        sector = await self._service.get_sector_summary()
        data: dict[str, Any] = {
            "title": "Market Overview Report",
            "report_type": "market",
            "generated_at": datetime.now(UTC).isoformat(),
            "date": date or "",
            "overview": overview.value if overview.success else {},
            "top_gainers": [self._serialize_quote(q) for q in (gainers.value if gainers.success else [])],
            "top_losers": [self._serialize_quote(q) for q in (losers.value if losers.success else [])],
            "most_active": [self._serialize_quote(q) for q in (active.value if active.success else [])],
            "sector_summary": sector.value if sector.success else [],
        }
        return Result.ok(data)

    def _serialize_quote(self, quote: Any) -> dict[str, Any]:
        return {
            "symbol": getattr(quote, "symbol", ""),
            "price_last": getattr(quote, "price_last", 0),
            "price_change_pct": getattr(quote, "price_change_pct", 0),
            "volume": getattr(quote, "volume", 0),
            "value": getattr(quote, "value", 0),
        }
