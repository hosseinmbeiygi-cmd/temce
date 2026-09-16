from __future__ import annotations

import contextlib
import csv
import json
from io import StringIO
from typing import Any

from core.logging import get_logger
from providers.base.parser_base import ParserBase

logger = get_logger(__name__)


class FileArchiveParser(ParserBase):
    def parse(self, raw_data: Any) -> list[dict[str, Any]]:
        fmt = raw_data.get("format", "csv") if isinstance(raw_data, dict) else "csv"
        content = raw_data.get("raw", raw_data) if isinstance(raw_data, dict) else raw_data

        if fmt == "csv":
            return self._parse_csv(content)
        elif fmt == "json":
            return self._parse_json(content)
        elif fmt == "excel":
            return self._parse_excel(content)
        return self._parse_csv(content)

    def _parse_csv(self, content: str | list[dict[str, Any]]) -> list[dict[str, Any]]:
        if isinstance(content, list):
            return content
        rows: list[dict[str, Any]] = []
        reader = csv.DictReader(StringIO(content))
        for row in reader:
            parsed: dict[str, Any] = {}
            for k, v in row.items():
                parsed[k.strip()] = self._coerce(v) if v else None
            rows.append(parsed)
        return rows

    def _parse_json(self, content: str | list[dict[str, Any]]) -> list[dict[str, Any]]:
        if isinstance(content, list):
            return content
        data = json.loads(content)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        if isinstance(data, dict):
            return [data]
        return []

    def _parse_excel(self, content: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return content

    def _coerce(self, value: str) -> int | float | str:
        with contextlib.suppress(ValueError):
            return int(value)
        with contextlib.suppress(ValueError):
            return float(value)
        return value

    def validate(self, parsed: list[dict[str, Any]]) -> bool:
        return len(parsed) > 0
