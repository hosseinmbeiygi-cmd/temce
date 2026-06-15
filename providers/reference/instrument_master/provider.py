from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.reference import ReferenceDataProvider
from providers.reference.instrument_master.client import InstrumentMasterClient
from providers.reference.instrument_master.instrument_mapper import InstrumentMapper
from providers.reference.instrument_master.market_classifier import MarketClassifier
from providers.reference.instrument_master.normalizer import InstrumentNormalizer

logger = get_logger(__name__)


class InstrumentMasterProvider(ReferenceDataProvider):
    def __init__(self) -> None:
        super().__init__(name="instrument_master")
        self.client = InstrumentMasterClient()
        self.mapper = InstrumentMapper()
        self.normalizer = InstrumentNormalizer()
        self.classifier = MarketClassifier()
        self._cache: dict[str, dict[str, Any]] = {}

    async def fetch(self, symbol: str | None = None, **kwargs: Any) -> Result[Any]:
        if symbol:
            return await self.get_instrument(symbol)
        return await self.get_all_instruments()

    async def get_instrument(self, symbol: str, **kwargs: Any) -> Result[dict[str, Any]]:
        if symbol in self._cache:
            return Result.ok(self._cache[symbol])
        result = await self.client.search_instruments(symbol)
        if result.success:
            raw = result.value.json() if hasattr(result.value, "json") else result.value
            instruments = raw if isinstance(raw, list) else raw.get("instruments", [])
            for inst in instruments:
                mapped = self.mapper.map(inst)
                normalized = self.normalizer.normalize_instrument(mapped)
                normalized["market_type"] = self.classifier.classify_market(normalized).value
                normalized["sector"] = self.classifier.classify_sector(normalized)
                if normalized.get("symbol") == symbol.upper():
                    self._cache[symbol] = normalized
                    return Result.ok(normalized)
            return Result.fail(f"Instrument not found: {symbol}")
        return Result.fail(result.error or "Unknown error")

    async def search_instruments(self, query: str, limit: int = 20, **kwargs: Any) -> Result[list[dict[str, Any]]]:
        result = await self.client.search_instruments(query)
        if result.success:
            raw = result.value.json() if hasattr(result.value, "json") else result.value
            instruments = raw if isinstance(raw, list) else raw.get("instruments", [])
            results = []
            for inst in instruments[:limit]:
                mapped = self.mapper.map(inst)
                normalized = self.normalizer.normalize_instrument(mapped)
                results.append(normalized)
            return Result.ok(results)
        return Result.fail(result.error or "Unknown error")

    async def get_all_instruments(self, **kwargs: Any) -> Result[list[dict[str, Any]]]:
        result = await self.client.get_all_instruments()
        if result.success:
            raw = result.value.json() if hasattr(result.value, "json") else result.value
            instruments = raw if isinstance(raw, list) else raw.get("instruments", [])
            results = []
            for inst in instruments:
                mapped = self.mapper.map(inst)
                normalized = self.normalizer.normalize_instrument(mapped)
                normalized["market_type"] = self.classifier.classify_market(normalized).value
                normalized["sector"] = self.classifier.classify_sector(normalized)
                results.append(normalized)
            return Result.ok(results)
        return Result.fail(result.error or "Unknown error")

    async def health(self) -> dict[str, Any]:
        result = await self.client.get_all_instruments()
        return {"healthy": result.success, "message": "ok" if result.success else result.error}
