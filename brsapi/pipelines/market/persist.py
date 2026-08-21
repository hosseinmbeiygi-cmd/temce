from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from core.time import now_iran

logger = get_logger(__name__)


class MarketDataPersister:
    def __init__(
        self,
        quote_repository: Any | None = None,
        trade_repository: Any | None = None,
        orderbook_repository: Any | None = None,
    ) -> None:
        self.quote_repo = quote_repository
        self.trade_repo = trade_repository
        self.orderbook_repo = orderbook_repository

    async def persist_quote(self, data: dict[str, Any]) -> Result[Any]:
        if self.quote_repo is None:
            return Result.ok(data)
        result = await self.quote_repo.save(data)
        if result.success:
            logger.debug("Persisted quote for %s", data.get("instrument_id", "?"))
        return result

    async def persist_trade(self, data: dict[str, Any]) -> Result[Any]:
        if self.trade_repo is None:
            return Result.ok(data)
        result = await self.trade_repo.save(data)
        if result.success:
            logger.debug("Persisted trade %s", data.get("trade_id", "?"))
        return result

    async def persist_orderbook(self, data: dict[str, Any]) -> Result[Any]:
        if self.orderbook_repo is None:
            return Result.ok(data)
        result = await self.orderbook_repo.save(data)
        if result.success:
            logger.debug("Persisted orderbook for %s", data.get("instrument_id", "?"))
        return result

    async def persist_batch(self, records: list[dict[str, Any]], record_type: str = "quote") -> Result[int]:
        persister = {
            "quote": self.persist_quote,
            "trade": self.persist_trade,
            "orderbook": self.persist_orderbook,
        }.get(record_type, self.persist_quote)
        count = 0
        for record in records:
            result = await persister(record)
            if result.success:
                count += 1
        logger.info("Persisted %d/%d %s records", count, len(records), record_type)
        return Result.ok(count)

    def record_lineage(self, instrument_id: str, source: str, record_type: str, count: int) -> dict[str, Any]:
        return {
            "instrument_id": instrument_id,
            "source": source,
            "record_type": record_type,
            "count": count,
            "timestamp": now_iran().isoformat(),
        }
