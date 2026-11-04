"""Macro/sentiment source providers."""

from providers.macro_sources.base import MacroSourceError, MacroSourceProvider
from providers.macro_sources.cftc import CFTCClient, build_default_cftc_client
from providers.macro_sources.economic_calendar import (
    EconomicCalendarProvider,
    SeededEconomicCalendarProvider,
)
from providers.macro_sources.fred import (
    FRED_DXY_BROAD_SERIES,
    FRED_TIPS_10Y_SERIES,
    FREDClient,
    build_default_fred_client,
)
from providers.macro_sources.tokenized_gold import (
    PREMIUM_INDICATOR_SUFFIX,
    TOKENIZED_GOLD_CATEGORY,
    TOKENIZED_GOLD_TICKERS,
    BrsApiTokenizedGoldProvider,
    GoldSpotPriceProvider,
    StoredGoldSpotProvider,
    TokenizedGoldProvider,
    compute_tokenized_gold_premium,
)

__all__ = [
    "CFTCClient",
    "EconomicCalendarProvider",
    "FREDClient",
    "FRED_DXY_BROAD_SERIES",
    "FRED_TIPS_10Y_SERIES",
    "MacroSourceError",
    "MacroSourceProvider",
    "PREMIUM_INDICATOR_SUFFIX",
    "SeededEconomicCalendarProvider",
    "TOKENIZED_GOLD_CATEGORY",
    "TOKENIZED_GOLD_TICKERS",
    "BrsApiTokenizedGoldProvider",
    "GoldSpotPriceProvider",
    "StoredGoldSpotProvider",
    "TokenizedGoldProvider",
    "build_default_cftc_client",
    "build_default_fred_client",
    "compute_tokenized_gold_premium",
]
