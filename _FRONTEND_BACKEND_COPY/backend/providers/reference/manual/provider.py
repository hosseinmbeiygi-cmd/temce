from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.reference import ReferenceDataProvider
from providers.reference.manual.file_importer import FileImporter
from providers.reference.manual.form_parser import FormParser

logger = get_logger(__name__)


class ManualReferenceProvider(ReferenceDataProvider):
    def __init__(self) -> None:
        super().__init__(name="manual_reference")
        self.form_parser = FormParser()
        self.file_importer = FileImporter()
        self._instruments: dict[str, dict[str, Any]] = {}

    async def fetch(self, symbol: str | None = None, **kwargs: Any) -> Result[Any]:
        if symbol:
            return await self.get_instrument(symbol)
        return await self.get_all_instruments()

    async def get_instrument(self, symbol: str, **kwargs: Any) -> Result[dict[str, Any]]:
        inst = self._instruments.get(symbol.upper())
        if inst:
            return Result.ok(inst)
        return Result.fail(f"Instrument not found: {symbol}")

    async def search_instruments(self, query: str, limit: int = 20, **kwargs: Any) -> Result[list[dict[str, Any]]]:
        results = []
        for inst in self._instruments.values():
            if query.upper() in inst.get("symbol", "").upper() or query in inst.get("name", ""):
                results.append(inst)
                if len(results) >= limit:
                    break
        return Result.ok(results)

    async def get_all_instruments(self, **kwargs: Any) -> Result[list[dict[str, Any]]]:
        return Result.ok(list(self._instruments.values()))

    async def add_instrument(self, form_data: dict[str, Any]) -> Result[dict[str, Any]]:
        errors = self.form_parser.validate_instrument_form(form_data)
        if errors:
            return Result.fail("; ".join(errors))
        parsed = self.form_parser.parse_instrument_form(form_data)
        self._instruments[parsed["symbol"]] = parsed
        logger.info("Added manual instrument: %s", parsed["symbol"])
        return Result.ok(parsed)

    async def remove_instrument(self, symbol: str) -> Result[bool]:
        removed = self._instruments.pop(symbol.upper(), None)
        if removed:
            return Result.ok(True)
        return Result.fail(f"Instrument not found: {symbol}")

    async def import_from_file(self, path: str) -> Result[int]:
        from pathlib import Path

        result = await self.file_importer.import_file(Path(path))
        if result.success and result.value:
            count = 0
            for row in result.value:
                add_result = await self.add_instrument(row)
                if add_result.success:
                    count += 1
            return Result.ok(count)
        return Result.fail(result.error or "Import failed")

    async def health(self) -> dict[str, Any]:
        return {"healthy": True, "message": f"{len(self._instruments)} manual instruments"}
