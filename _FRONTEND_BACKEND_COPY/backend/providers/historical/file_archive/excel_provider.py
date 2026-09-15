from __future__ import annotations

from pathlib import Path
from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.base_provider import BaseProvider
from providers.historical.file_archive.mapping import FileArchiveMapping
from providers.historical.file_archive.parser import FileArchiveParser

logger = get_logger(__name__)


try:
    import openpyxl

    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False
    logger.warning("openpyxl not installed; ExcelArchiveProvider unavailable")


class ExcelArchiveProvider(BaseProvider):
    def __init__(self, archive_dir: str | Path | None = None) -> None:
        super().__init__(name="excel_archive")
        self.archive_dir = Path(archive_dir) if archive_dir else Path.cwd() / "data" / "archives"
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.mapping = FileArchiveMapping()
        self.parser = FileArchiveParser()

    def _symbol_path(self, symbol: str) -> Path:
        return self.archive_dir / f"{symbol}.xlsx"

    async def fetch(self, symbol: str | None = None, **kwargs: Any) -> Result[Any]:
        if not HAS_OPENPYXL:
            return Result.fail("openpyxl is required for Excel support")
        if not symbol:
            return Result.fail("symbol is required")
        path = self._symbol_path(symbol)
        if not path.exists():
            return Result.fail(f"File not found: {path}")
        try:
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            ws = wb.active
            rows: list[dict[str, Any]] = []
            headers: list[str] = []
            for i, row in enumerate(ws.iter_row()):
                if i == 0:
                    headers = [str(c.value) if c.value else f"col_{j}" for j, c in enumerate(row)]
                else:
                    rows.append({headers[j]: c.value for j, c in enumerate(row)})
            wb.close()
            parsed = self.parser.parse({"raw": rows, "format": "excel"})
            return Result.ok(self.mapping.map(parsed))
        except Exception as e:
            logger.error("Excel read failed for %s: %s", symbol, e)
            return Result.fail(str(e))

    async def save(self, symbol: str, data: list[dict[str, Any]]) -> Result[Path]:
        if not HAS_OPENPYXL:
            return Result.fail("openpyxl is required for Excel support")
        path = self._symbol_path(symbol)
        try:
            from openpyxl import Workbook

            wb = Workbook()
            ws = wb.active
            if data:
                headers = list(data[0].keys())
                ws.append(headers)
                for row in data:
                    ws.append([row.get(h) for h in headers])
            wb.save(str(path))
            wb.close()
            logger.info("Saved %d rows to %s", len(data), path)
            return Result.ok(path)
        except Exception as e:
            logger.error("Excel save failed for %s: %s", symbol, e)
            return Result.fail(str(e))

    async def health(self) -> dict[str, Any]:
        return {"healthy": self.archive_dir.exists() and HAS_OPENPYXL, "message": f"archive_dir={self.archive_dir}"}
