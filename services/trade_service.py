from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class TradeService:
    async def get_trades(self, symbol: str, limit: int = 100) -> Result[list[dict[str, Any]]]:
        return Result.ok([])

    async def get_recent(self, symbol: str) -> Result[list[dict[str, Any]]]:
        return Result.ok([])

    async def save_trade(self, data: dict[str, Any]) -> Result[dict[str, Any]]:
        return Result.ok(data)
