from __future__ import annotations

import contextlib
import csv
from io import StringIO
from typing import Any

from core.logging import get_logger
from providers.base.parser_base import ParserBase

logger = get_logger(__name__)


class TseArchiveParser(ParserBase):
    def parse(self, raw_data: Any) -> list[dict[str, Any]]:
        if isinstance(raw_data, list):
            return raw_data
        if isinstance(raw_data, dict):
            if "data" in raw_data:
                return self._parse_csv(raw_data["data"])
            return [raw_data]
        if isinstance(raw_data, str):
            return self._parse_csv(raw_data)
        return []

    def _parse_csv(self, content: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        reader = csv.DictReader(StringIO(content))
        for row in reader:
            parsed: dict[str, Any] = {}
            for k, v in row.items():
                key = k.strip() if k else ""
                parsed[key] = self._clean_value(v) if v else None
            rows.append(parsed)
        return rows

    def _clean_value(self, value: str) -> int | float | str:
        value = value.strip().replace(",", "")
        with contextlib.suppress(ValueError):
            return int(value)
        with contextlib.suppress(ValueError):
            return float(value)
        return value

    def validate(self, parsed: list[dict[str, Any]]) -> bool:
        return len(parsed) > 0
