from __future__ import annotations

import contextlib
from typing import Any

from core.logging import get_logger
from providers.base.parser_base import ParserBase

logger = get_logger(__name__)


class TseReferenceParser(ParserBase):
    def parse(self, raw_data: Any) -> list[dict[str, Any]]:
        if isinstance(raw_data, list):
            return raw_data
        if isinstance(raw_data, dict):
            if "data" in raw_data:
                return raw_data["data"]
            if "instruments" in raw_data:
                return raw_data["instruments"]
            return [raw_data]
        if isinstance(raw_data, str):
            return self._parse_tsv(raw_data)
        return []

    def _parse_tsv(self, content: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        lines = content.strip().split("\n")
        if not lines:
            return rows
        headers = lines[0].split("\t")
        for line in lines[1:]:
            if not line.strip():
                continue
            values = line.split("\t")
            row = {}
            for i, header in enumerate(headers):
                value = values[i] if i < len(values) else ""
                row[header.strip()] = self._clean(value)
            rows.append(row)
        return rows

    def _clean(self, value: str) -> str | int | float:
        value = value.strip()
        with contextlib.suppress(ValueError):
            return int(value.replace(",", ""))
        with contextlib.suppress(ValueError):
            return float(value.replace(",", ""))
        return value if value else ""

    def validate(self, parsed: list[dict[str, Any]]) -> bool:
        return len(parsed) > 0
