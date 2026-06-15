from __future__ import annotations

from abc import ABC, abstractmethod

from .instruments import InstrumentInfo


class InstrumentFilter(ABC):
    @abstractmethod
    def apply(self, instruments: list[InstrumentInfo]) -> list[InstrumentInfo]:
        ...


class MarketFilter(InstrumentFilter):
    def __init__(self, *markets: str) -> None:
        self._markets = set(markets)

    def apply(self, instruments: list[InstrumentInfo]) -> list[InstrumentInfo]:
        return [i for i in instruments if i.market in self._markets]


class TypeFilter(InstrumentFilter):
    def __init__(self, *types: str) -> None:
        self._types = set(types)

    def apply(self, instruments: list[InstrumentInfo]) -> list[InstrumentInfo]:
        return [i for i in instruments if i.instrument_type in self._types]


class GroupFilter(InstrumentFilter):
    def __init__(self, *group_codes: str) -> None:
        self._groups = set(group_codes)

    def apply(self, instruments: list[InstrumentInfo]) -> list[InstrumentInfo]:
        return [i for i in instruments if i.group_code in self._groups]


class StatusFilter(InstrumentFilter):
    def __init__(self, status: str = "active") -> None:
        self._status = status

    def apply(self, instruments: list[InstrumentInfo]) -> list[InstrumentInfo]:
        return [i for i in instruments if i.status == self._status]


class LiquidityFilter(InstrumentFilter):
    def __init__(self, min_avg_volume: int = 100_000, min_trade_count: int = 10) -> None:
        self._min_volume = min_avg_volume
        self._min_trades = min_trade_count

    def apply(self, instruments: list[InstrumentInfo]) -> list[InstrumentInfo]:
        if not hasattr(self, "_volume_data"):
            return instruments
        return [
            i
            for i in instruments
            if self._volume_data.get(i.id, 0) >= self._min_volume
        ]

    def set_volume_data(self, data: dict[str, int]) -> None:
        self._volume_data = data


class PriceFilter(InstrumentFilter):
    def __init__(self, min_price: float = 0.0, max_price: float = float("inf")) -> None:
        self._min = min_price
        self._max = max_price

    def apply(self, instruments: list[InstrumentInfo]) -> list[InstrumentInfo]:
        if not hasattr(self, "_price_data"):
            return instruments
        return [
            i
            for i in instruments
            if self._min <= self._price_data.get(i.id, 0) <= self._max
        ]

    def set_price_data(self, data: dict[str, float]) -> None:
        self._price_data = data


class CompositeFilter(InstrumentFilter):
    def __init__(self, *filters: InstrumentFilter) -> None:
        self._filters = list(filters)

    def apply(self, instruments: list[InstrumentInfo]) -> list[InstrumentInfo]:
        result = instruments
        for f in self._filters:
            result = f.apply(result)
        return result
