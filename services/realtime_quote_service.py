from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class RealTimeQuoteService:
    async def get_latest(self, instrument_id: str) -> Result[dict[str, Any]]:
        return Result.fail(f"No quote for {instrument_id}")

    async def get_latest_batch(self, instrument_ids: list[str]) -> Result[dict[str, list[dict[str, Any]]]]:
        return Result.ok({})

    async def stream(self, instrument_ids: list[str]) -> Result[None]:
        return Result.ok(None)
