"""Backtest Strategy Composer: generates millions of strategy combinations from 30 indicators."""

from backtesting.composer.indicator_registry import REGISTRY, get_indicator, list_all_indicators
from backtesting.composer.pre_filter import PreTestFilter
from backtesting.composer.quality_filter import QualityFilter
from backtesting.composer.strategy_composer import StrategyBlueprint, StrategyComposer

__all__ = [
    "REGISTRY",
    "get_indicator",
    "list_all_indicators",
    "StrategyComposer",
    "StrategyBlueprint",
    "PreTestFilter",
    "QualityFilter",
]
