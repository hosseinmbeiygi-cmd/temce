"""Gold module schemas — Iranian gold market (ETFs, futures, physical, signals)."""

from schemas.api.gold.analytics import (
    AedParityRequest,
    AssayAdjustmentRequest,
    Black76Request,
    CoinBubblesRequest,
    EnrichChainRequest,
    FuturesTermRequest,
    ImeArbitrageRequest,
    ImpliedVolatilityRequest,
    MacroPostureRequest,
    MesghalPriceRequest,
    OptionsChainRequest,
    RiskPosition,
    RiskScenarioInput,
    RiskShockSet,
    RiskStressRequest,
)
from schemas.api.gold.coin_bubble import (
    CoinBubbleRequest,
    CoinBubbleResponse,
)
from schemas.api.gold.etf import (
    ETFNavPremiumResponse,
    ETFNavPremiumRow,
    ETFSymbol,
    ETFUniverse,
)
from schemas.api.gold.futures import (
    FuturesHealthResponse,
    FuturesMarginRequest,
    FuturesMarginResponse,
    FuturesPosition,
)
from schemas.api.gold.live import (
    GoldLivePrices,
    GoldLivePricesRequest,
)
from schemas.api.gold.signals import (
    GoldKillSwitchStatus,
    GoldSignal,
    GoldSignalAction,
    GoldSignalTimeframe,
)

__all__ = [
    "AedParityRequest",
    "AssayAdjustmentRequest",
    "Black76Request",
    "CoinBubbleRequest",
    "CoinBubblesRequest",
    "CoinBubbleResponse",
    "ETFNavPremiumResponse",
    "ETFNavPremiumRow",
    "ETFSymbol",
    "ETFUniverse",
    "FuturesHealthResponse",
    "FuturesMarginRequest",
    "FuturesMarginResponse",
    "FuturesPosition",
    "FuturesTermRequest",
    "GoldLivePrices",
    "GoldLivePricesRequest",
    "GoldKillSwitchStatus",
    "GoldSignal",
    "GoldSignalAction",
    "GoldSignalTimeframe",
    "ImeArbitrageRequest",
    "ImpliedVolatilityRequest",
    "MacroPostureRequest",
    "MesghalPriceRequest",
    "OptionsChainRequest",
    "EnrichChainRequest",
    "RiskPosition",
    "RiskScenarioInput",
    "RiskShockSet",
    "RiskStressRequest",
]
