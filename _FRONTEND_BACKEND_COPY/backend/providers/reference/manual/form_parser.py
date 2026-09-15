from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class FormParser:
    def parse_instrument_form(self, form_data: dict[str, Any]) -> dict[str, Any]:
        return {
            "symbol": form_data.get("symbol", "").strip().upper(),
            "name": form_data.get("name", "").strip(),
            "market": form_data.get("market", "bours").strip().lower(),
            "sector": form_data.get("sector", "").strip(),
            "eps": self._parse_number(form_data.get("eps")),
            "base_volume": self._parse_number(form_data.get("base_volume")),
            "shares": self._parse_number(form_data.get("shares")),
            "description": form_data.get("description", "").strip(),
            "source": form_data.get("source", "manual"),
        }

    def parse_alias_form(self, form_data: dict[str, Any]) -> dict[str, Any]:
        return {
            "canonical": form_data.get("canonical", "").strip().upper(),
            "alias": form_data.get("alias", "").strip().upper(),
            "description": form_data.get("description", "").strip(),
        }

    def _parse_number(self, value: Any) -> int | float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return value
        try:
            return int(str(value).replace(",", ""))
        except ValueError:
            try:
                return float(str(value).replace(",", ""))
            except ValueError:
                return None

    def validate_instrument_form(self, form_data: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not form_data.get("symbol"):
            errors.append("symbol is required")
        if not form_data.get("name"):
            errors.append("name is required")
        return errors
