from __future__ import annotations

"""Data source registry — maps each market to its canonical data source.

This module is the single point of truth for which source provides
data for each market type. When adding a new market or changing a
source, only this file needs updating.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DataSourceSpec:
    market: str
    primary_source: str
    fallback_source: str | None = None
    requires_adjustment: bool = True  # dividend/capital increase adjustment
    requires_delisting_check: bool = True
    typical_frequency_seconds: int = 86400  # daily
    min_history_days: int = 30
    notes: str = ""


DATA_SOURCE_REGISTRY: dict[str, DataSourceSpec] = {
    "stock": DataSourceSpec(
        market="stock",
        primary_source="brsapi_historical_daily",
        fallback_source="tsetmc",
        requires_adjustment=True,
        requires_delisting_check=True,
        min_history_days=252,
        notes="TSETMC + Codal for corporate actions",
    ),
    "gold": DataSourceSpec(
        market="gold",
        primary_source="brsapi_gold_coin_prices",
        fallback_source="ime.co.ir",
        requires_adjustment=False,
        requires_delisting_check=False,
        min_history_days=90,
        notes="Gold coin and bullion prices; spread is the primary cost",
    ),
    "currency": DataSourceSpec(
        market="currency",
        primary_source="brsapi_currency_prices",
        fallback_source="tgju.org",
        requires_adjustment=False,
        requires_delisting_check=False,
        min_history_days=90,
        notes="Free market USD/IRR + official rates",
    ),
    "crypto": DataSourceSpec(
        market="crypto",
        primary_source="brsapi_crypto_prices",
        fallback_source=None,
        requires_adjustment=False,
        requires_delisting_check=False,
        min_history_days=30,
        notes="Major crypto pairs; access restrictions may apply",
    ),
    "ime": DataSourceSpec(
        market="ime",
        primary_source="brsapi_ime_physical_trades",
        fallback_source="ime.co.ir",
        requires_adjustment=False,
        requires_delisting_check=False,
        min_history_days=90,
        notes="Iran Mercantile Exchange physical commodities",
    ),
    "option": DataSourceSpec(
        market="option",
        primary_source="brsapi_options_chain",
        fallback_source=None,
        requires_adjustment=False,
        requires_delisting_check=True,
        min_history_days=30,
        notes="Options chain data; IV derived from HV when unavailable",
    ),
}


def get_source(market: str) -> DataSourceSpec:
    """Get the canonical data source specification for a market.

    Raises KeyError if the market is not registered.
    """
    if market not in DATA_SOURCE_REGISTRY:
        raise KeyError(
            f"Unknown market '{market}'. Known: {list(DATA_SOURCE_REGISTRY.keys())}"
        )
    return DATA_SOURCE_REGISTRY[market]


def register_source(market: str, spec: DataSourceSpec) -> None:
    """Register or override a data source specification (runtime)."""
    DATA_SOURCE_REGISTRY[market] = spec


def validate_market_data(
    market: str,
    n_days: int,
    n_symbols: int = 1,
) -> list[str]:
    """Validate that a market has sufficient data for backtesting.

    Returns a list of warning messages (empty if all checks pass).
    """
    warnings: list[str] = []
    try:
        spec = get_source(market)
    except KeyError as e:
        return [str(e)]

    if n_days < spec.min_history_days:
        warnings.append(
            f"Market '{market}': {n_days} days < minimum {spec.min_history_days} days"
        )
    if n_symbols < 5:
        warnings.append(
            f"Market '{market}': only {n_symbols} symbol(s); "
            "low diversification may lead to overfitting"
        )
    return warnings
