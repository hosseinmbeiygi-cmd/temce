from __future__ import annotations

from typing import Any

import pandas as pd

from .base_adapter import BaseLibraryAdapter, CollectedData


class SadraTseAdapter(BaseLibraryAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.source_name = "sadra_tse"

    def get_capabilities(self) -> dict[str, bool]:
        return {
            "micro_trades": True,
            "market_depth": True,
            "price_history": True,
        }

    def collect_symbol(self, symbol: str) -> list[CollectedData]:
        results: list[CollectedData] = []

        try:
            from sadra_tse import SadraTse
            client = SadraTse()
            trades = client.get_trades(symbol)
            results.append(CollectedData(self.source_name, symbol, "micro_trades", trades))
        except Exception as e:
            self.handle_error(e, f"{symbol}/micro_trades")

        try:
            from sadra_tse import SadraTse
            client = SadraTse()
            depth = client.get_market_depth(symbol)
            results.append(CollectedData(self.source_name, symbol, "market_depth", depth))
        except Exception as e:
            self.handle_error(e, f"{symbol}/market_depth")

        try:
            from sadra_tse import SadraTse
            client = SadraTse()
            history = client.get_price_history(symbol)
            results.append(CollectedData(self.source_name, symbol, "price_history", history))
        except Exception as e:
            self.handle_error(e, f"{symbol}/price_history")

        return results
