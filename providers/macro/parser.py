from __future__ import annotations

from typing import Any


class MacroParser:
    """Parser for macroeconomic indicators."""

    def parse_inflation(self, data: dict[str, Any]) -> dict[str, Any]:
        result = dict(data)
        try:
            result["value"] = float(data.get("value", 0))
        except (ValueError, TypeError):
            result["value"] = 0.0
        return result

    def parse_unemployment(self, data: dict[str, Any]) -> dict[str, Any]:
        result = dict(data)
        try:
            result["value"] = float(data.get("value", 0))
        except (ValueError, TypeError):
            result["value"] = 0.0
        return result

    def parse_gdp(self, data: dict[str, Any]) -> dict[str, Any]:
        result = dict(data)
        try:
            result["value"] = float(data.get("value", 0))
        except (ValueError, TypeError):
            result["value"] = 0.0
        return result

    def parse_date(self, date_str: str) -> str:
        return date_str

    def format_value(self, value: float, format_type: str) -> float:
        return value
