from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

INDICATOR_OVERLAY = "overlay"
INDICATOR_OSCILLATOR = "oscillator"
INDICATOR_VOLUME = "volume"
INDICATOR_VOLATILITY = "volatility"
INDICATOR_STRENGTH = "strength"
INDICATOR_MOMENTUM = "momentum"
INDICATOR_TREND = "trend"
INDICATOR_CUSTOM = "custom"

# Market type categories
MARKET_COMMON = "common"
MARKET_STOCK = "stock"
MARKET_COMMODITY = "commodity"
MARKET_ENERGY = "energy"
MARKET_OPTION = "option"
MARKET_FUTURES = "futures"
MARKET_DEBT = "debt"
MARKET_FUND = "fund"
MARKET_MICROSTRUCTURE = "microstructure"
MARKET_INTERMARKET = "intermarket"
MARKET_STATISTICAL = "statistical"
MARKET_SCORING = "scoring"

# Signal direction
SIGNAL_BULLISH = "bullish"
SIGNAL_BEARISH = "bearish"
SIGNAL_NEUTRAL = "neutral"
SIGNAL_BULLISH_BEARISH = "bullish_bearish"
SIGNAL_POSITIVE = "positive"
SIGNAL_NEGATIVE = "negative"


@dataclass
class IndicatorMeta:
    name: str = ""
    display_name: str = ""
    category: str = ""
    subcategory: str = ""
    market_type: str = ""
    formula: str = ""
    formula_latex: str = ""
    interpretation: str = ""
    threshold: str = ""
    application: str = ""
    caveat: str = ""
    signal_direction: str = SIGNAL_NEUTRAL
    default_parameters: dict[str, Any] = field(default_factory=dict)
    min_inputs: int = 1
    max_inputs: int = 1
    plot_style: str = "line"
    metadata: dict[str, Any] = field(default_factory=dict)
