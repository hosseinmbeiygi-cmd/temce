"""Declarative market registry.

Single source of truth for which markets the platform models, which venue each
belongs to, and how far its data integration has progressed.

Adding a market later means filling ``data_sources`` and flipping
``integration_status``; callers do not change. A market with
``IntegrationStatus.PLANNED`` or ``PLACEHOLDER`` is deliberately modelled but
not fully fed yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.constants import AssetClass, MarketType
from core.enums.instruments import CommodityKind, DerivativeUnderlying


class MarketSegment(StrEnum):
    EQUITY = "equity"
    FIXED_INCOME = "fixed_income"
    SUKUK = "sukuk"
    FUND = "fund"
    ETF = "etf"
    DERIVATIVE = "derivative"
    CURRENCY = "currency"
    COMMODITY = "commodity"


class IntegrationStatus(StrEnum):
    INTEGRATED = "integrated"    # enum + model + adapter + live feed
    PLACEHOLDER = "placeholder"  # modelled, but the feed/provider is incomplete
    PLANNED = "planned"          # enum/model only, no data source at all


@dataclass(frozen=True)
class MarketDefinition:
    market_type: MarketType
    segment: MarketSegment
    asset_class: AssetClass
    venue: str
    integration_status: IntegrationStatus
    data_sources: tuple[str, ...] = ()
    settlement: str | None = None
    underlying: DerivativeUnderlying | None = None
    commodity_kinds: tuple[CommodityKind, ...] = ()
    notes: str = ""


MARKET_REGISTRY: dict[MarketType, MarketDefinition] = {
    MarketType.BOURS: MarketDefinition(
        market_type=MarketType.BOURS,
        segment=MarketSegment.EQUITY,
        asset_class=AssetClass.EQUITY,
        venue="TSE",
        integration_status=IntegrationStatus.INTEGRATED,
        data_sources=("tsetmc", "tse"),
        settlement="T+2",
    ),
    MarketType.STOCK: MarketDefinition(
        market_type=MarketType.STOCK,
        segment=MarketSegment.EQUITY,
        asset_class=AssetClass.EQUITY,
        venue="TSE",
        integration_status=IntegrationStatus.INTEGRATED,
        data_sources=("tsetmc", "tse"),
        settlement="T+2",
        notes="Legacy alias for the TSE equity market.",
    ),
    MarketType.FARABOURS: MarketDefinition(
        market_type=MarketType.FARABOURS,
        segment=MarketSegment.EQUITY,
        asset_class=AssetClass.EQUITY,
        venue="IFB",
        integration_status=IntegrationStatus.INTEGRATED,
        data_sources=("tsetmc", "tse"),
        settlement="T+2",
    ),
    MarketType.PAYEH: MarketDefinition(
        market_type=MarketType.PAYEH,
        segment=MarketSegment.EQUITY,
        asset_class=AssetClass.EQUITY,
        venue="IFB base market",
        integration_status=IntegrationStatus.INTEGRATED,
        data_sources=("tsetmc",),
        settlement="T+2",
    ),
    MarketType.OPTION: MarketDefinition(
        market_type=MarketType.OPTION,
        segment=MarketSegment.DERIVATIVE,
        asset_class=AssetClass.DERIVATIVE,
        venue="TSE derivatives",
        integration_status=IntegrationStatus.INTEGRATED,
        data_sources=("tsetmc",),
        settlement="T+2",
        underlying=DerivativeUnderlying.EQUITY,
    ),
    MarketType.FUTURES: MarketDefinition(
        market_type=MarketType.FUTURES,
        segment=MarketSegment.DERIVATIVE,
        asset_class=AssetClass.DERIVATIVE,
        venue="IME / IRFX",
        integration_status=IntegrationStatus.PLACEHOLDER,
        data_sources=("tsetmc",),
        settlement="daily_mark_to_market",
        underlying=DerivativeUnderlying.COMMODITY,
        notes="Generic snapshot only; no dedicated futures feed or open-interest stream.",
    ),
    MarketType.ETF: MarketDefinition(
        market_type=MarketType.ETF,
        segment=MarketSegment.ETF,
        asset_class=AssetClass.FUND,
        venue="TSE / IFB",
        integration_status=IntegrationStatus.INTEGRATED,
        data_sources=("tsetmc",),
        settlement="T+2",
    ),
    MarketType.SUKUK: MarketDefinition(
        market_type=MarketType.SUKUK,
        segment=MarketSegment.SUKUK,
        asset_class=AssetClass.SUKUK,
        venue="TSE / IFB fixed-income board",
        integration_status=IntegrationStatus.PLANNED,
        data_sources=(),
        settlement="T+2",
        notes=(
            "No board feed is wired. Codal only carries prospectuses, not prices. "
            "Needs an issuer/board reference source and a clean/dirty price feed."
        ),
    ),
    MarketType.FX: MarketDefinition(
        market_type=MarketType.FX,
        segment=MarketSegment.CURRENCY,
        asset_class=AssetClass.CURRENCY,
        venue="IRFX / OTC",
        integration_status=IntegrationStatus.PLACEHOLDER,
        data_sources=("brsapi",),
        settlement="T+2",
        underlying=DerivativeUnderlying.CURRENCY,
        notes="BrsApi covers spot rates; the IRFX currency-futures feed is not wired.",
    ),
    MarketType.COMMODITY: MarketDefinition(
        market_type=MarketType.COMMODITY,
        segment=MarketSegment.COMMODITY,
        asset_class=AssetClass.COMMODITY,
        venue="IME",
        integration_status=IntegrationStatus.PLACEHOLDER,
        data_sources=("brsapi",),
        settlement="physical",
        commodity_kinds=(
            CommodityKind.ENERGY,
            CommodityKind.PRECIOUS_METAL,
            CommodityKind.BASE_METAL,
            CommodityKind.AGRICULTURAL,
            CommodityKind.PETROCHEMICAL,
            CommodityKind.CERTIFICATE,
        ),
        notes=(
            "BrsApi supplies global commodity quotes. IME venue data (spot, "
            "futures, certificates) is not wired; agricultural providers are placeholders."
        ),
    ),
}


def get_market_definition(market_type: MarketType | str) -> MarketDefinition:
    if isinstance(market_type, str):
        market_type = MarketType(market_type)
    try:
        return MARKET_REGISTRY[market_type]
    except KeyError:
        raise KeyError(f"No registry entry for market type: {market_type}") from None


def markets_by_status(status: IntegrationStatus | str) -> tuple[MarketDefinition, ...]:
    if isinstance(status, str):
        status = IntegrationStatus(status)
    return tuple(definition for definition in MARKET_REGISTRY.values() if definition.integration_status == status)


def markets_requiring_integration() -> tuple[MarketDefinition, ...]:
    """Markets that are modelled but not yet fully fed."""
    return tuple(
        definition
        for definition in MARKET_REGISTRY.values()
        if definition.integration_status != IntegrationStatus.INTEGRATED
    )


__all__ = [
    "MARKET_REGISTRY",
    "IntegrationStatus",
    "MarketDefinition",
    "MarketSegment",
    "get_market_definition",
    "markets_by_status",
    "markets_requiring_integration",
]
