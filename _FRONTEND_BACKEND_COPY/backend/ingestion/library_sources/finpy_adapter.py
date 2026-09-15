from __future__ import annotations

import finpy_tse as fpy

from .base_adapter import BaseLibraryAdapter, CollectedData


class FinpyAdapter(BaseLibraryAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.source_name = "finpy"

    def get_capabilities(self) -> dict[str, bool]:
        return {
            "price_history": True,
            "intraday_trades": True,
            "orderbook": True,
            "realtime": True,
            "indexes": True,
            "real_individual": True,
            "symbols_list": True,
        }

    def collect_symbol(self, symbol: str) -> list[CollectedData]:
        results: list[CollectedData] = []

        try:
            df = fpy.Get_Price_History(stock=symbol, adjust_price=True)
            results.append(CollectedData(self.source_name, symbol, "price_history", df))
        except Exception as e:
            self.handle_error(e, f"{symbol}/price_history")

        try:
            df = fpy.Get_Tick_Data(symbol)
            results.append(CollectedData(self.source_name, symbol, "intraday_trades", df))
        except Exception as e:
            self.handle_error(e, f"{symbol}/intraday_trades")

        try:
            df = fpy.Get_Order_Book(symbol)
            results.append(CollectedData(self.source_name, symbol, "orderbook", df))
        except Exception as e:
            self.handle_error(e, f"{symbol}/orderbook")

        try:
            df = fpy.Get_Real_Time(symbol)
            results.append(CollectedData(self.source_name, symbol, "realtime", df))
        except Exception as e:
            self.handle_error(e, f"{symbol}/realtime")

        try:
            df = fpy.Get_Real_Individual(symbol)
            results.append(CollectedData(self.source_name, symbol, "real_individual", df))
        except Exception as e:
            self.handle_error(e, f"{symbol}/real_individual")

        return results
