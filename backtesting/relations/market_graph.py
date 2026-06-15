from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class MarketRelation(StrEnum):
    CORRELATED = "correlated"
    ARBITRAGE = "arbitrage"
    SAME_SECTOR = "same_sector"
    CROSS_LISTED = "cross_listed"


@dataclass
class MarketCorrelation:
    market_a: str
    market_b: str
    correlation: float = 0.0
    lag: int = 0


class MarketGraph:
    BOURSE = "bourse"
    FARABOURSE = "farabourse"
    ENERGY = "energy"
    OPTIONS = "options"
    FUTURES = "futures"

    def __init__(self) -> None:
        self._correlations: dict[tuple[str, str], MarketCorrelation] = {}
        self._relations: dict[str, dict[str, set[str]]] = {}

    def add_correlation(self, market_a: str, market_b: str, correlation: float, lag: int = 0) -> None:
        key = tuple(sorted([market_a, market_b]))
        self._correlations[key] = MarketCorrelation(
            market_a=market_a,
            market_b=market_b,
            correlation=correlation,
            lag=lag,
        )

    def get_correlation(self, market_a: str, market_b: str) -> MarketCorrelation | None:
        key = tuple(sorted([market_a, market_b]))
        return self._correlations.get(key)

    def get_all_markets(self) -> list[str]:
        markets: set[str] = set()
        for corr in self._correlations.values():
            markets.add(corr.market_a)
            markets.add(corr.market_b)
        return sorted(markets)

    def instruments_in_market(self, market: str, universe: Any) -> list[Any]:
        return universe.by_market(market)

    def arbitrage_pairs(self, min_correlation: float = 0.8) -> list[tuple[str, str, float]]:
        pairs: list[tuple[str, str, float]] = []
        for _key, corr in self._correlations.items():
            if abs(corr.correlation) >= min_correlation:
                pairs.append((corr.market_a, corr.market_b, corr.correlation))
        return pairs
