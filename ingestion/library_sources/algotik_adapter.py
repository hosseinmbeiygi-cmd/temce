from __future__ import annotations

from typing import Any

from .base_adapter import BaseLibraryAdapter, CollectedData


class AlgotikAdapter(BaseLibraryAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.source_name = "algotik"
        self._client: Any = None
        self._init_client()

    def _init_client(self) -> None:
        try:
            from algotik_tse import AlgotikTse
            self._client = AlgotikTse()
        except ImportError:
            self.handle_error(ImportError("algotik_tse not installed"))

    def get_capabilities(self) -> dict[str, bool]:
        return {
            "price": True,
            "currency": True,
            "gold": True,
            "commodities": True,
            "indices": True,
        }

    def collect_symbol(self, symbol: str) -> list[CollectedData]:
        results: list[CollectedData] = []
        if self._client is None:
            return results

        try:
            price = self._client.get_price(symbol)
            results.append(CollectedData(self.source_name, symbol, "price", price))
        except Exception as e:
            self.handle_error(e, f"{symbol}/price")

        return results

    def collect_currency(self) -> list[CollectedData]:
        results: list[CollectedData] = []
        if self._client is None:
            return results
        try:
            data = self._client.get_all_currency()
            results.append(CollectedData(self.source_name, "currency", "currency", data))
        except Exception as e:
            self.handle_error(e, "currency")
        return results

    def collect_gold(self) -> list[CollectedData]:
        results: list[CollectedData] = []
        if self._client is None:
            return results
        try:
            data = self._client.get_gold_price()
            results.append(CollectedData(self.source_name, "gold", "gold", data))
        except Exception as e:
            self.handle_error(e, "gold")
        return results
