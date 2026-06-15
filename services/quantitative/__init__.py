"""Quantitative Analysis Engine for Iranian Capital Markets.

A comprehensive, PhD-level quantitative analysis framework covering
all 5 Iranian capital markets under the SEO umbrella:

  1. Bourse (Tehran Stock Exchange) — Equities
  2. Farabourse (OTC Market)        — Equities
  3. Commodity Exchange (IME)       — Physical commodities
  4. Energy Exchange (IEE)          — Energy products
  5. Derivatives Market             — Options & Futures

Each market has its own scoring engine with proper Z-Score normalisation,
weighted component scores and interpretable phase classification.
"""

from services.quantitative.bonds import (
    BondAnalyzer,
    BondIndicators,
    BondScoreResult,
)
from services.quantitative.commodity import (
    CommodityAnalyzer,
    CommodityIndicators,
    CommodityScoreResult,
)
from services.quantitative.derivatives import (
    FuturesAnalyzer,
    FuturesScoreResult,
    OptionGreeks,
    OptionsAnalyzer,
    OptionsScoreResult,
)
from services.quantitative.energy import (
    EnergyAnalyzer,
    EnergyIndicators,
    EnergyScoreResult,
)
from services.quantitative.funds import (
    FundAnalyzer,
    FundIndicators,
    FundScoreResult,
)
from services.quantitative.general import (
    calculate_alpha,
    calculate_amihud_illiquidity,
    calculate_atr,
    calculate_beta,
    calculate_bollinger_bandwidth,
    calculate_clv,
    calculate_compression_ratio,
    calculate_correlation,
    calculate_daily_range,
    calculate_excess_return,
    calculate_float_turnover,
    calculate_log_return,
    calculate_normalized_volatility,
    calculate_recovery_ratio,
    calculate_relative_range,
    calculate_relative_strength,
    calculate_relative_volume,
    calculate_rolling_window,
    calculate_simple_return,
    calculate_traded_value,
    calculate_true_range,
    calculate_volume_zscore,
    calculate_weighted_score,
    calculate_zscore,
)
from services.quantitative.intermarket import (
    IntermarketAnalyzer,
    IntermarketResult,
)
from services.quantitative.microstructure import (
    MicrostructureAnalyzer,
    MicrostructureResult,
)
from services.quantitative.normalizer import (
    MinMaxClipped,
    RobustScaler,
    SigmoidNormalizer,
    ZScoreNormalizer,
)
from services.quantitative.scoring import (
    MarketPhase,
    MarketScoreResult,
    MarketScoringEngine,
)
from services.quantitative.statistical import (
    RegimeDetector,
    StatisticalModels,
)
from services.quantitative.stocks import (
    StockAnalyzer,
    StockIndicators,
    StockScoreResult,
)

__all__ = [
    # Normalizers
    "ZScoreNormalizer",
    "MinMaxClipped",
    "SigmoidNormalizer",
    "RobustScaler",
    # General
    "calculate_simple_return",
    "calculate_log_return",
    "calculate_daily_range",
    "calculate_relative_range",
    "calculate_clv",
    "calculate_recovery_ratio",
    "calculate_relative_volume",
    "calculate_volume_zscore",
    "calculate_traded_value",
    "calculate_float_turnover",
    "calculate_amihud_illiquidity",
    "calculate_true_range",
    "calculate_atr",
    "calculate_normalized_volatility",
    "calculate_compression_ratio",
    "calculate_bollinger_bandwidth",
    "calculate_relative_strength",
    "calculate_excess_return",
    "calculate_zscore",
    "calculate_beta",
    "calculate_alpha",
    "calculate_correlation",
    "calculate_rolling_window",
    "calculate_weighted_score",
    # Stocks
    "StockAnalyzer",
    "StockIndicators",
    "StockScoreResult",
    # Microstructure
    "MicrostructureAnalyzer",
    "MicrostructureResult",
    # Commodity
    "CommodityAnalyzer",
    "CommodityIndicators",
    "CommodityScoreResult",
    # Energy
    "EnergyAnalyzer",
    "EnergyIndicators",
    "EnergyScoreResult",
    # Derivatives
    "OptionsAnalyzer",
    "FuturesAnalyzer",
    "OptionGreeks",
    "OptionsScoreResult",
    "FuturesScoreResult",
    # Bonds
    "BondAnalyzer",
    "BondIndicators",
    "BondScoreResult",
    # Funds
    "FundAnalyzer",
    "FundIndicators",
    "FundScoreResult",
    # Intermarket
    "IntermarketAnalyzer",
    "IntermarketResult",
    # Statistical
    "StatisticalModels",
    "RegimeDetector",
    # Scoring
    "MarketScoringEngine",
    "MarketScoreResult",
    "MarketPhase",
]
