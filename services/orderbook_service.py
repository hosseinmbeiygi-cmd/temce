from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class OrderBookService:
    async def get_orderbook(self, symbol: str) -> Result[dict[str, Any]]:
        return Result.fail(f"No orderbook for {symbol}")

    async def get_history(self, symbol: str, limit: int = 100) -> Result[list[dict[str, Any]]]:
        return Result.ok([])

    async def save_snapshot(self, symbol: str, data: dict[str, Any]) -> Result[dict[str, Any]]:
        return Result.ok(data)
