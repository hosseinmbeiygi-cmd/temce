"""OrderBook Service — uses real orderbook data from brsapi_symbol_snapshots.

No mock/hardcoded orderbook. The 5-level bid/ask data comes directly
from the AllSymbols snapshot which contains orderbook levels.
"""

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
        """Get real orderbook from brsapi_symbol_snapshots."""
        # Try from the snapshot table first (already synced data)
        if self._brsapi:
            try:
                snap = await self._brsapi.get_symbol_snapshot(symbol)
                if snap:
                    orderbook = self._snapshot_to_orderbook(snap, symbol)
                    if orderbook:
                        return Result.ok(orderbook)
            except Exception:
                logger.exception("Snapshot orderbook fetch failed for %s", symbol)

        # Try live fetch from API
        if self._client:
            try:
                live = await self._fetch_live_orderbook(symbol)
                if live:
                    return Result.ok(live)
            except Exception:
                logger.exception("Live orderbook fetch failed for %s", symbol)

        return Result.fail(f"Orderbook not available for {symbol} — no snapshot data found")

    def _snapshot_to_orderbook(self, snap: dict[str, Any], symbol: str) -> dict[str, Any] | None:
        """Extract 5-level orderbook from brsapi_symbol_snapshots row."""
        bids = []
        asks = []

        for i in range(1, 6):
            bid_price = float(snap.get(f"bid_price_{i}") or 0)
            bid_vol = int(snap.get(f"bid_volume_{i}") or 0)
            bid_cnt = int(snap.get(f"bid_count_{i}") or 0)
            if bid_price > 0:
                bids.append({"price": bid_price, "volume": bid_vol, "count": bid_cnt})

            ask_price = float(snap.get(f"ask_price_{i}") or 0)
            ask_vol = int(snap.get(f"ask_volume_{i}") or 0)
            ask_cnt = int(snap.get(f"ask_count_{i}") or 0)
            if ask_price > 0:
                asks.append({"price": ask_price, "volume": ask_vol, "count": ask_cnt})

        if not bids and not asks:
            return None

        best_bid = bids[0]["price"] if bids else 0
        best_ask = asks[0]["price"] if asks else 0
        spread = best_ask - best_bid if best_bid and best_ask else 0
        spread_pct = round(spread / best_bid * 100, 2) if best_bid else 0

        return {
            "symbol": symbol,
            "bids": bids,
            "asks": asks,
            "spread": spread,
            "spread_pct": spread_pct,
        }

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
                        {
                            "price": sym_data.get("bid_price_1") or 0,
                            "volume": sym_data.get("bid_volume_1") or 0,
                            "count": sym_data.get("bid_count_1") or 0,
                        },
                        {
                            "price": sym_data.get("bid_price_2") or 0,
                            "volume": sym_data.get("bid_volume_2") or 0,
                            "count": sym_data.get("bid_count_2") or 0,
                        },
                        {
                            "price": sym_data.get("bid_price_3") or 0,
                            "volume": sym_data.get("bid_volume_3") or 0,
                            "count": sym_data.get("bid_count_3") or 0,
                        },
                        {
                            "price": sym_data.get("bid_price_4") or 0,
                            "volume": sym_data.get("bid_volume_4") or 0,
                            "count": sym_data.get("bid_count_4") or 0,
                        },
                        {
                            "price": sym_data.get("bid_price_5") or 0,
                            "volume": sym_data.get("bid_volume_5") or 0,
                            "count": sym_data.get("bid_count_5") or 0,
                        },
                    ],
                    "asks": [
                        {
                            "price": sym_data.get("ask_price_1") or 0,
                            "volume": sym_data.get("ask_volume_1") or 0,
                            "count": sym_data.get("ask_count_1") or 0,
                        },
                        {
                            "price": sym_data.get("ask_price_2") or 0,
                            "volume": sym_data.get("ask_volume_2") or 0,
                            "count": sym_data.get("ask_count_2") or 0,
                        },
                        {
                            "price": sym_data.get("ask_price_3") or 0,
                            "volume": sym_data.get("ask_volume_3") or 0,
                            "count": sym_data.get("ask_count_3") or 0,
                        },
                        {
                            "price": sym_data.get("ask_price_4") or 0,
                            "volume": sym_data.get("ask_volume_4") or 0,
                            "count": sym_data.get("ask_count_4") or 0,
                        },
                        {
                            "price": sym_data.get("ask_price_5") or 0,
                            "volume": sym_data.get("ask_volume_5") or 0,
                            "count": sym_data.get("ask_count_5") or 0,
                        },
                    ],
                    "spread": (sym_data.get("ask_price_1") or 0) - (sym_data.get("bid_price_1") or 0),
                    "spread_pct": round(
                        ((sym_data.get("ask_price_1") or 0) - (sym_data.get("bid_price_1") or 0))
                        / (sym_data.get("bid_price_1") or 1)
                        * 100,
                        2,
                    ),
                }
        return None

    async def get_history(self, symbol: str, limit: int = 100) -> Result[list[dict[str, Any]]]:
        """Get historical daily data from brsapi_historical_daily."""
        if not self._session:
            return Result.ok([])

        from sqlalchemy import text

        try:
            q = text("""
                SELECT symbol, date, price_first as price_open, price_close,
                       price_max as price_high, price_min as price_low,
                       price_last, trade_volume as volume, trade_value as value
                FROM brsapi_historical_daily
                WHERE symbol = :sym
                ORDER BY date DESC
                LIMIT :lim
            """)
            result = await self._session.execute(q, {"sym": symbol, "lim": limit})
            rows = [dict(row._mapping) for row in result.fetchall()]
            return Result.ok(rows)
        except Exception:
            logger.exception("Failed to fetch history for %s", symbol)
            return Result.ok([])

    async def save_snapshot(self, symbol: str, data: dict[str, Any]) -> Result[dict[str, Any]]:
        return Result.ok(data)
