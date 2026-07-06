from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class OrderBookService:
    def __init__(
        self,
        session: AsyncSession | None = None,
        brsapi_query_service: Any = None,
        brsapi_client: Any = None,
    ) -> None:
        self._session = session
        self._brsapi = brsapi_query_service
        self._client = brsapi_client

    async def get_orderbook(self, symbol: str) -> Result[dict[str, Any]]:
        if self._client:
            try:
                live = await self._fetch_live_orderbook(symbol)
                if live:
                    return Result.ok(live)
            except Exception:
                logger.exception("Live orderbook fetch failed for %s", symbol)
        return Result.ok(self._mock_orderbook(symbol))

    async def _fetch_live_orderbook(self, symbol: str) -> dict[str, Any] | None:
        """Fetch orderbook for a symbol from BrsApi API."""
        snap = None
        if self._brsapi:
            snap = await self._brsapi.get_symbol_snapshot(symbol)
        l18 = snap.get("l18") if snap else None
        if not l18:
            return None

        from brsapi.config import BrsApiEndpoints
        from brsapi.parsers import TsetmcParser

        result = await self._client.fetch(
            BrsApiEndpoints.ALL_SYMBOLS,
            params={"type": "1"},
        )
        if not result.success or not result.value or not result.value.data:
            return None

        parsed = TsetmcParser.parse_all_symbols(result.value.data)
        if not isinstance(parsed, list):
            return None

        for sym_data in parsed:
            if sym_data.get("l18") == l18:
                return {
                    "symbol": symbol,
                    "bids": [
                        {"price": sym_data.get("bid_price_1") or 0, "volume": sym_data.get("bid_volume_1") or 0, "count": sym_data.get("bid_count_1") or 0},
                        {"price": sym_data.get("bid_price_2") or 0, "volume": sym_data.get("bid_volume_2") or 0, "count": sym_data.get("bid_count_2") or 0},
                        {"price": sym_data.get("bid_price_3") or 0, "volume": sym_data.get("bid_volume_3") or 0, "count": sym_data.get("bid_count_3") or 0},
                        {"price": sym_data.get("bid_price_4") or 0, "volume": sym_data.get("bid_volume_4") or 0, "count": sym_data.get("bid_count_4") or 0},
                        {"price": sym_data.get("bid_price_5") or 0, "volume": sym_data.get("bid_volume_5") or 0, "count": sym_data.get("bid_count_5") or 0},
                    ],
                    "asks": [
                        {"price": sym_data.get("ask_price_1") or 0, "volume": sym_data.get("ask_volume_1") or 0, "count": sym_data.get("ask_count_1") or 0},
                        {"price": sym_data.get("ask_price_2") or 0, "volume": sym_data.get("ask_volume_2") or 0, "count": sym_data.get("ask_count_2") or 0},
                        {"price": sym_data.get("ask_price_3") or 0, "volume": sym_data.get("ask_volume_3") or 0, "count": sym_data.get("ask_count_3") or 0},
                        {"price": sym_data.get("ask_price_4") or 0, "volume": sym_data.get("ask_volume_4") or 0, "count": sym_data.get("ask_count_4") or 0},
                        {"price": sym_data.get("ask_price_5") or 0, "volume": sym_data.get("ask_volume_5") or 0, "count": sym_data.get("ask_count_5") or 0},
                    ],
                    "spread": (sym_data.get("ask_price_1") or 0) - (sym_data.get("bid_price_1") or 0),
                    "spread_pct": round(((sym_data.get("ask_price_1") or 0) - (sym_data.get("bid_price_1") or 0)) / (sym_data.get("bid_price_1") or 1) * 100, 2),
                }
        return None

    @staticmethod
    def _mock_orderbook(symbol: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "bids": [
                {"price": 15000, "volume": 50000, "count": 12},
                {"price": 14950, "volume": 35000, "count": 8},
                {"price": 14900, "volume": 42000, "count": 15},
                {"price": 14850, "volume": 28000, "count": 6},
                {"price": 14800, "volume": 55000, "count": 20},
            ],
            "asks": [
                {"price": 15100, "volume": 45000, "count": 10},
                {"price": 15150, "volume": 32000, "count": 7},
                {"price": 15200, "volume": 48000, "count": 14},
                {"price": 15250, "volume": 25000, "count": 5},
                {"price": 15300, "volume": 60000, "count": 18},
            ],
            "spread": 100,
            "spread_pct": 0.67,
        }

    async def get_history(self, symbol: str, limit: int = 100) -> Result[list[dict[str, Any]]]:
        return Result.ok([])

    async def save_snapshot(self, symbol: str, data: dict[str, Any]) -> Result[dict[str, Any]]:
        return Result.ok(data)
