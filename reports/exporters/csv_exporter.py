from __future__ import annotations

import csv
import io
from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class CsvExporter:
    def __init__(self, delimiter: str = ",", encoding: str = "utf-8-sig"):
        self._delimiter = delimiter
        self._encoding = encoding

    async def export(self, data: list[dict[str, Any]], output_path: str = "") -> Result[str]:
        if not data:
            return Result.fail("No data to export")
        fieldnames = list(data[0].keys())
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=self._delimiter)
        writer.writeheader()
        writer.writerows(data)
        content = output.getvalue()
        if output_path:
            with open(output_path, "w", encoding=self._encoding, newline="") as f:
                f.write(content)
            return Result.ok(output_path)
        return Result.ok(content)

    async def export_to_bytes(self, data: list[dict[str, Any]]) -> Result[bytes]:
        if not data:
            return Result.fail("No data to export")
        fieldnames = list(data[0].keys())
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=self._delimiter)
        writer.writeheader()
        writer.writerows(data)
        content = output.getvalue().encode(self._encoding)
        return Result.ok(content)
