from __future__ import annotations

from typing import Any


class ManualProvider:
    """Provider for manually submitted market data."""

    def __init__(self) -> None:
        self._submissions: list[dict[str, Any]] = []

    def submit_quote(self, symbol: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = {"symbol": symbol, **payload, "status": "submitted"}
        self._submissions.append(result)
        return result

    def submit_trade(self, symbol: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = {"symbol": symbol, **payload, "status": "submitted"}
        self._submissions.append(result)
        return result

    def validate(self, data: dict[str, Any]) -> bool:
        return "symbol" in data

    def batch_submit(self, items: list[dict[str, Any]], data_type: str = "quote") -> list[dict[str, Any]]:
        results = []
        for item in items:
            if data_type == "quote":
                result = self.submit_quote(item.get("symbol", ""), item)
            else:
                result = self.submit_trade(item.get("symbol", ""), item)
            results.append(result)
        return results

    def list_submissions(self) -> list[dict[str, Any]]:
        return list(self._submissions)
