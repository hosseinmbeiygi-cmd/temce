from domain.indicators.definitions import (
    MARKET_COMMODITY,
    MARKET_COMMON,
    MARKET_DEBT,
    MARKET_ENERGY,
    MARKET_FUND,
    MARKET_FUTURES,
    MARKET_INTERMARKET,
    MARKET_MICROSTRUCTURE,
    MARKET_OPTION,
    MARKET_SCORING,
    MARKET_STATISTICAL,
    MARKET_STOCK,
    IndicatorMeta,
)
from domain.indicators.entities import IndicatorDefinition, IndicatorValue
from domain.indicators.parameters import IndicatorParameter
from domain.indicators.registry import ALL_INDICATORS

__all__ = [
    "IndicatorDefinition",
    "IndicatorValue",
    "IndicatorParameter",
    "IndicatorMeta",
    "MARKET_COMMON",
    "MARKET_STOCK",
    "MARKET_COMMODITY",
    "MARKET_ENERGY",
    "MARKET_OPTION",
    "MARKET_FUTURES",
    "MARKET_DEBT",
    "MARKET_FUND",
    "MARKET_MICROSTRUCTURE",
    "MARKET_INTERMARKET",
    "MARKET_STATISTICAL",
    "MARKET_SCORING",
    "ALL_INDICATORS",
]


def get_indicators_by_market(market_type: str) -> list[IndicatorMeta]:
    return ALL_INDICATORS.get(market_type, [])


def get_indicator_by_name(name: str) -> IndicatorMeta | None:
    for indicators in ALL_INDICATORS.values():
        for ind in indicators:
            if ind.name == name:
                return ind
    return None
