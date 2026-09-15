from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.reference import ReferenceDataProvider
from providers.reference.codal.client import CodalClient
from providers.reference.codal.mapping import CodalMapping
from providers.reference.codal.parser import CodalParser

logger = get_logger(__name__)


class CodalProvider(ReferenceDataProvider):
    def __init__(self) -> None:
        super().__init__(name="codal")
        self.client = CodalClient()
        self.parser = CodalParser()
        self.mapping = CodalMapping()

    async def fetch(self, symbol: str | None = None, **kwargs: Any) -> Result[Any]:
        if not symbol:
            return Result.fail("symbol is required")
        return await self.get_instrument(symbol)

    async def get_instrument(self, symbol: str, **kwargs: Any) -> Result[dict[str, Any]]:
        result = await self.client.get_company_reports(symbol, limit=1)
        if result.success:
            raw = result.value.json() if hasattr(result.value, "json") else result.value
            parsed = self.parser.parse(raw)
            mapped = self.mapping.map_batch(parsed)
            return Result.ok(mapped[0] if mapped else {})
        return Result.fail(result.error or "Unknown error")

    async def search_instruments(self, query: str, limit: int = 20, **kwargs: Any) -> Result[list[dict[str, Any]]]:
        result = await self.client.search_reports(query, limit=limit)
        if result.success:
            raw = result.value.json() if hasattr(result.value, "json") else result.value
            parsed = self.parser.parse(raw)
            return Result.ok(self.mapping.map_batch(parsed))
        return Result.fail(result.error or "Unknown error")

    async def get_all_instruments(self, **kwargs: Any) -> Result[list[dict[str, Any]]]:
        return Result.fail("Codal does not provide a complete instrument list")

    async def health(self) -> dict[str, Any]:
        result = await self.client.search_reports("test", limit=1)
        return {"healthy": result.success, "message": "ok" if result.success else result.error}
