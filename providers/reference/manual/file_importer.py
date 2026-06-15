from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class FileImporter:
    def __init__(self) -> None:
        self.supported_formats = ["csv", "json", "xlsx"]

    async def import_file(self, path: Path) -> Result[list[dict[str, Any]]]:
        if not path.exists():
            return Result.fail(f"File not found: {path}")
        ext = path.suffix.lower()
        if ext == ".csv":
            return await self._import_csv(path)
        elif ext == ".json":
            return await self._import_json(path)
        elif ext == ".xlsx":
            return await self._import_excel(path)
        return Result.fail(f"Unsupported format: {ext}")

    async def _import_csv(self, path: Path) -> Result[list[dict[str, Any]]]:
        try:
            with open(path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = [dict(row) for row in reader]
            return Result.ok(rows)
        except Exception as e:
            return Result.fail(f"CSV import failed: {e}")

    async def _import_json(self, path: Path) -> Result[list[dict[str, Any]]]:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return Result.ok(data)
            if isinstance(data, dict) and "data" in data:
                return Result.ok(data["data"])
            return Result.ok([data])
        except Exception as e:
            return Result.fail(f"JSON import failed: {e}")

    async def _import_excel(self, path: Path) -> Result[list[dict[str, Any]]]:
        try:
            import openpyxl

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
            return Result.ok(rows)
        except ImportError:
            return Result.fail("openpyxl is required for Excel import")
        except Exception as e:
            return Result.fail(f"Excel import failed: {e}")
