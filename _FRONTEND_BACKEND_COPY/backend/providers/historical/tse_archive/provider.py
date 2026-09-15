from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.base_provider import BaseProvider
from providers.historical.tse_archive.client import TseArchiveClient
from providers.historical.tse_archive.mapping import TseArchiveMapping
from providers.historical.tse_archive.parser import TseArchiveParser

logger = get_logger(__name__)


class TseArchiveProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__(name="tse_archive")
        self.client = TseArchiveClient()
        self.parser = TseArchiveParser()
        self.mapping = TseArchiveMapping()

    async def fetch(self, symbol: str | None = None, **kwargs: Any) -> Result[Any]:
        if not symbol:
            return Result.fail("symbol is required")
        ticker_id = kwargs.get("ticker_id", symbol)
        days = kwargs.get("days", 365)
        result = await self.client.get_price_history(ticker_id, days)
        if not result.success:
            return result
        raw = result.value.json() if hasattr(result.value, "json") else result.value
        data = self.parser.parse(raw)
        mapped = self.mapping.map_batch(data)
        return Result.ok(mapped)

    async def health(self) -> dict[str, Any]:
        result = await self.client.get_price_history("test", 1)
        return {"healthy": result.success, "message": "ok" if result.success else result.error}
