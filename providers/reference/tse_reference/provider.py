from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.reference import ReferenceDataProvider
from providers.reference.tse_reference.client import TseReferenceClient
from providers.reference.tse_reference.mapping import TseReferenceMapping
from providers.reference.tse_reference.parser import TseReferenceParser

logger = get_logger(__name__)


class TseReferenceProvider(ReferenceDataProvider):
    def __init__(self) -> None:
        super().__init__(name="tse_reference")
        self.client = TseReferenceClient()
        self.parser = TseReferenceParser()
        self.mapping = TseReferenceMapping()

    async def fetch(self, symbol: str | None = None, **kwargs: Any) -> Result[Any]:
        if symbol:
            return await self.get_instrument(symbol)
        return await self.get_all_instruments()

    async def get_instrument(self, symbol: str, **kwargs: Any) -> Result[dict[str, Any]]:
        result = await self.client.get_instrument_list()
        if result.success:
            raw = result.value.text if hasattr(result.value, "text") else result.value
            instruments = self.parser.parse(raw)
            for inst in instruments:
                mapped = self.mapping.map(inst)
                if mapped.get("symbol") == symbol.upper():
                    return Result.ok(mapped)
            return Result.fail(f"Instrument not found: {symbol}")
        return Result.fail(result.error or "Unknown error")

    async def search_instruments(self, query: str, limit: int = 20, **kwargs: Any) -> Result[list[dict[str, Any]]]:
        result = await self.client.get_instrument_list()
        if result.success:
            raw = result.value.text if hasattr(result.value, "text") else result.value
            instruments = self.parser.parse(raw)
            results = []
            for inst in instruments:
                mapped = self.mapping.map(inst)
                if query.upper() in mapped.get("symbol", "").upper() or query in mapped.get("name", ""):
                    results.append(mapped)
                    if len(results) >= limit:
                        break
            return Result.ok(results)
        return Result.fail(result.error or "Unknown error")

    async def get_all_instruments(self, **kwargs: Any) -> Result[list[dict[str, Any]]]:
        result = await self.client.get_instrument_list()
        if result.success:
            raw = result.value.text if hasattr(result.value, "text") else result.value
            instruments = self.parser.parse(raw)
            return Result.ok(self.mapping.map_batch(instruments))
        return Result.fail(result.error or "Unknown error")

    async def health(self) -> dict[str, Any]:
        result = await self.client.get_instrument_list()
        return {"healthy": result.success, "message": "ok" if result.success else result.error}
