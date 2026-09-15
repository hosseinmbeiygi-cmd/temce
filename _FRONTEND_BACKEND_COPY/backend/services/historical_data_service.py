from __future__ import annotations

from datetime import date
from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class HistoricalDataService:
    async def get_quotes(
        self, instrument_id: str, start_date: date, end_date: date, timeframe: str = "1d"
    ) -> Result[list[dict[str, Any]]]:
        return Result.ok([])

    async def backfill(self, instrument_id: str, start_date: date, end_date: date) -> Result[int]:
        return Result.ok(0)

    async def get_candles(self, instrument_id: str, timeframe: str, limit: int = 100) -> Result[list[dict[str, Any]]]:
        return Result.ok([])
