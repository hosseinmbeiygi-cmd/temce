from domain.indicators.registry.commodity import COMMODITY_INDICATORS
from domain.indicators.registry.common import COMMON_INDICATORS
from domain.indicators.registry.debt import DEBT_INDICATORS
from domain.indicators.registry.derivatives import FUTURES_INDICATORS, OPTION_INDICATORS
from domain.indicators.registry.energy import ENERGY_INDICATORS
from domain.indicators.registry.fund import FUND_INDICATORS
from domain.indicators.registry.intermarket import INTERMARKET_INDICATORS
from domain.indicators.registry.microstructure import MICROSTRUCTURE_INDICATORS
from domain.indicators.registry.scoring import SCORING_MODELS
from domain.indicators.registry.statistical import STATISTICAL_INDICATORS
from domain.indicators.registry.stock import STOCK_INDICATORS

ALL_INDICATORS: dict[str, list] = {
    "common": COMMON_INDICATORS,
    "stock": STOCK_INDICATORS,
    "commodity": COMMODITY_INDICATORS,
    "energy": ENERGY_INDICATORS,
    "option": OPTION_INDICATORS,
    "futures": FUTURES_INDICATORS,
    "debt": DEBT_INDICATORS,
    "fund": FUND_INDICATORS,
    "microstructure": MICROSTRUCTURE_INDICATORS,
    "intermarket": INTERMARKET_INDICATORS,
    "statistical": STATISTICAL_INDICATORS,
    "scoring": SCORING_MODELS,
}

__all__ = [
    "COMMON_INDICATORS",
    "STOCK_INDICATORS",
    "COMMODITY_INDICATORS",
    "ENERGY_INDICATORS",
    "OPTION_INDICATORS",
    "FUTURES_INDICATORS",
    "DEBT_INDICATORS",
    "FUND_INDICATORS",
    "MICROSTRUCTURE_INDICATORS",
    "INTERMARKET_INDICATORS",
    "STATISTICAL_INDICATORS",
    "SCORING_MODELS",
    "ALL_INDICATORS",
]
