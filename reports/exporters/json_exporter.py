from __future__ import annotations

import json
from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class JsonExporter:
    def __init__(self, indent: int = 2, ensure_ascii: bool = False):
        self._indent = indent
        self._ensure_ascii = ensure_ascii

    async def export(self, data: Any, output_path: str = "") -> Result[str]:
        content = json.dumps(data, indent=self._indent, ensure_ascii=self._ensure_ascii, default=str)
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)
            return Result.ok(output_path)
        return Result.ok(content)

    async def export_to_bytes(self, data: Any) -> Result[bytes]:
        content = json.dumps(data, indent=self._indent, ensure_ascii=self._ensure_ascii, default=str)
        return Result.ok(content.encode("utf-8"))

    async def export_pretty(self, data: Any, output_path: str = "") -> Result[str]:
        return await self.export(data, output_path)
