from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.base_provider import BaseProvider
from providers.historical.file_archive.mapping import FileArchiveMapping
from providers.historical.file_archive.parser import FileArchiveParser

logger = get_logger(__name__)


class CSVArchiveProvider(BaseProvider):
    def __init__(self, archive_dir: str | Path | None = None) -> None:
        super().__init__(name="csv_archive")
        self.archive_dir = Path(archive_dir) if archive_dir else Path.cwd() / "data" / "archives"
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.mapping = FileArchiveMapping()
        self.parser = FileArchiveParser()

    def _symbol_path(self, symbol: str) -> Path:
        return self.archive_dir / f"{symbol}.csv"

    async def fetch(self, symbol: str | None = None, **kwargs: Any) -> Result[Any]:
        if not symbol:
            return Result.fail("symbol is required")
        path = self._symbol_path(symbol)
        if not path.exists():
            return Result.fail(f"File not found: {path}")
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
            parsed = self.parser.parse({"raw": content, "format": "csv"})
            return Result.ok(self.mapping.map(parsed))
        except Exception as e:
            logger.error("CSV read failed for %s: %s", symbol, e)
            return Result.fail(str(e))

    async def save(self, symbol: str, data: list[dict[str, Any]]) -> Result[Path]:
        path = self._symbol_path(symbol)
        try:
            if not data:
                return Result.fail("No data to save")
            fieldnames = list(data[0].keys())
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
            logger.info("Saved %d rows to %s", len(data), path)
            return Result.ok(path)
        except Exception as e:
            logger.error("CSV save failed for %s: %s", symbol, e)
            return Result.fail(str(e))

    async def health(self) -> dict[str, Any]:
        return {"healthy": self.archive_dir.exists(), "message": f"archive_dir={self.archive_dir}"}
