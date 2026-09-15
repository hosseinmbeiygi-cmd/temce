"""Gold module schemas — Iranian gold market (ETFs, futures, physical, signals)."""

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
    "CoinBubbleRequest",
    "CoinBubbleResponse",
    "ETFNavPremiumResponse",
    "ETFNavPremiumRow",
    "ETFSymbol",
    "ETFUniverse",
    "FuturesHealthResponse",
    "FuturesMarginRequest",
    "FuturesMarginResponse",
    "FuturesPosition",
    "GoldLivePrices",
    "GoldLivePricesRequest",
    "GoldKillSwitchStatus",
    "GoldSignal",
    "GoldSignalAction",
    "GoldSignalTimeframe",
]
