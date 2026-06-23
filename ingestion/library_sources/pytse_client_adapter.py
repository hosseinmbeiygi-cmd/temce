from __future__ import annotations

from typing import Any

from .base_adapter import BaseLibraryAdapter, CollectedData


class PytseClientAdapter(BaseLibraryAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.source_name = "pytse_client"
        self._client: Any = None
        self._init_client()

    def _init_client(self) -> None:
        try:
            import pytse_client as tse
            self._client = tse
        except ImportError:
            self.handle_error(ImportError("pytse_client not installed"))

    def get_capabilities(self) -> dict[str, bool]:
        return {
            "ticker_info": True,
            "price_history": True,
            "client_types": True,
            "shareholders": True,
            "symbols_list": True,
        }

    def collect_symbol(self, symbol: str) -> list[CollectedData]:
        results: list[CollectedData] = []
        if self._client is None:
            return results

        try:
            ticker = self._client.Ticker(symbol)
            info = ticker.get_ticker_info()
            results.append(CollectedData(self.source_name, symbol, "ticker_info", info))
        except Exception as e:
            self.handle_error(e, f"{symbol}/ticker_info")

        try:
            history = ticker.get_ticker_history()
            results.append(CollectedData(self.source_name, symbol, "price_history", history))
        except Exception as e:
            self.handle_error(e, f"{symbol}/price_history")

        try:
            client_types = ticker.get_client_types()
            results.append(CollectedData(self.source_name, symbol, "client_types", client_types))
        except Exception as e:
            self.handle_error(e, f"{symbol}/client_types")

        return results
