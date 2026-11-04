"""Gold spot providers used by the resilient gold feed."""

from providers.gold_spot.base import GoldSpotProvider, GoldSpotProviderError
from providers.gold_spot.brsapi import BrsApiGoldSpotProvider
from providers.gold_spot.yahoo import YahooGoldSpotProvider


def build_default_gold_spot_providers() -> list[GoldSpotProvider]:
    """Return the production order: BrsApi primary, Yahoo backup."""
    return [BrsApiGoldSpotProvider(), YahooGoldSpotProvider()]


__all__ = [
    "BrsApiGoldSpotProvider",
    "GoldSpotProvider",
    "GoldSpotProviderError",
    "YahooGoldSpotProvider",
    "build_default_gold_spot_providers",
]
