from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class TradeService:
    def __init__(self, brsapi_query_service: Any, brsapi_client: Any = None) -> None:
        self._brsapi = brsapi_query_service
        self._client = brsapi_client

    async def get_trades(self, symbol: str, limit: int = 100) -> Result[list[dict[str, Any]]]:
        try:
            # ── Step 1: Try local DB (BrsApiQueryService) ──
            trades = await self._brsapi.get_intraday_trades(symbol, limit)
            if trades:
                return Result.ok(trades)

            # ── Step 2: DB empty → try live BrsApi API fetch ──
            if self._client:
                live_trades = await self._fetch_live_trades(symbol, limit)
                if live_trades:
                    return Result.ok(live_trades)

            return Result.ok([])
        except Exception as e:
            logger.exception("Failed to fetch trades for %s", symbol)
            return Result.ok([])

    async def _fetch_live_trades(self, symbol: str, limit: int) -> list[dict[str, Any]]:
        """Fetch intraday trades directly from the BrsApi API when DB is empty."""
        # Resolve symbol to l18 code via snapshot table
        snap = await self._brsapi.get_symbol_snapshot(symbol)
        l18 = snap.get("l18") if snap else None
        if not l18:
            logger.warning("No l18 code found for symbol %s — cannot fetch live trades", symbol)
            return []

        try:
            from brsapi.config import BrsApiEndpoints
            from brsapi.parsers import TsetmcParser

            result = await self._client.fetch(
                BrsApiEndpoints.TRANSACTION,
                params={"l18": l18},
            )
            if result.success and result.value and result.value.data:
                parsed = TsetmcParser.parse_transactions(result.value.data)
                if isinstance(parsed, list) and parsed:
                    # Save fetched data to DB for future reads
                    try:
                        await self._save_live_trades(symbol, parsed)
                    except Exception:
                        logger.warning("Failed to persist live trades for %s", symbol, exc_info=True)
                    return parsed[:limit]
        except Exception:
            logger.exception("Live fetch failed for %s", symbol)

        return []

    async def _save_live_trades(self, symbol: str, records: list[dict[str, Any]]) -> None:
        """Persist live-fetched trade records to the database for future reads."""
        from brsapi.models import IntradayTradeModel
        from brsapi.repositories import BulkUpsertRepository
        from core.database import get_session

        async for session in get_session():
            repo = BulkUpsertRepository(session, IntradayTradeModel)
            await repo.bulk_insert(records)
        # commit() fires after the async for loop completes naturally

    async def get_recent(self, symbol: str) -> Result[list[dict[str, Any]]]:
        try:
            trades = await self._brsapi.get_intraday_trades(symbol, 20)
            if trades:
                return Result.ok(trades)
            # Live fallback for recent endpoint too
            if self._client:
                live_trades = await self._fetch_live_trades(symbol, 20)
                if live_trades:
                    return Result.ok(live_trades)
            return Result.ok([])
        except Exception as e:
            logger.exception("Failed to fetch recent trades for %s", symbol)
            return Result.ok([])

    async def save_trade(self, data: dict[str, Any]) -> Result[dict[str, Any]]:
        """Persist a single trade record to the database."""
        try:
            from brsapi.models import IntradayTradeModel
            from brsapi.repositories import BulkUpsertRepository
            from core.database import get_session

            async for session in get_session():
                repo = BulkUpsertRepository(session, IntradayTradeModel)
                await repo.bulk_insert([data])
            # commit() fires after the async for loop completes naturally
            return Result.ok(data)
        except Exception as e:
            logger.exception("Failed to save trade record")
            return Result.fail(str(e))
