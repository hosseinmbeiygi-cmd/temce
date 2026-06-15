from __future__ import annotations

from typing import Any


class CodalParser:
    """Parser for Codal (Iranian corporate disclosure system) reports."""

    def parse_report(self, html: str) -> dict[str, Any]:
        return {"status": "parsed", "items": []}

    def parse_attachment_url(self, url: str) -> str:
        return url

    def parse_fiscal_period(self, period: str) -> str:
        return period

    def parse_audit_status(self, status: str) -> str:
        return status

    def extract_financial_summary(self, data: dict[str, Any]) -> dict[str, Any]:
        result = {}
        for key, value in data.items():
            try:
                result[key] = float(str(value).replace(",", ""))
            except (ValueError, TypeError):
                result[key] = value
        return result
