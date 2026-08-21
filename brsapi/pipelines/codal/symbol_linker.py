from __future__ import annotations

from typing import Any


class CodalSymbolLinker:
    """Linker for matching Codal reports to market symbols."""

    def __init__(self) -> None:
        self._isin_map: dict[str, str] = {
            "IRO1FOLD0001": "فولاد",
            "IRO1FMLI0001": "فملی",
        }
        self._company_map: dict[str, str] = {
            "فولاد مبارکه اصفهان": "فولاد",
            "فولاد مبارکه": "فولاد",
            "ملی صنایع مس ایران": "فملی",
            "ملی صنایع مس": "فملی",
        }

    def link_by_isin(self, isin: str) -> str | None:
        return self._isin_map.get(isin)

    def link_by_company_name(self, company_name: str) -> str | None:
        return self._company_map.get(company_name)

    def resolve(self, symbol_or_name: str) -> str | None:
        if symbol_or_name in self._isin_map.values():
            return symbol_or_name
        return self._company_map.get(symbol_or_name)

    def batch_link(self, reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
        results = []
        for report in reports:
            symbol = None
            if "isin" in report:
                symbol = self.link_by_isin(report["isin"])
            if symbol is None and "company" in report:
                symbol = self.link_by_company_name(report["company"])
            results.append({**report, "symbol": symbol})
        return results
