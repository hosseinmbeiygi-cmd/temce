"""Request and response schemas for the gold analytics calculators (Phases 1–4).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class MesghalPriceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mesghal_price: float = Field(..., gt=0, description="مظنهٔ مثقال ۱۷ عیار (ریال)")


class AssayAdjustmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weight_grams: float = Field(..., ge=0)
    assay: int = Field(..., gt=0, description="عیار وارد‌شده، مثلاً 705 / 750 / 900")
    base_gram18_price: float = Field(..., gt=0)


class CoinBubblesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ounce_usd: float = Field(..., gt=0)
    usd_irr: float = Field(..., gt=0)
    coin_prices: dict[str, float] = Field(
        ..., description="emami / half / quarter / gerami"
    )
    gerami_minting_fee_irr: float | None = Field(None, ge=0)


class ImeArbitrageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ime_cert_price_irr: float = Field(..., gt=0)
    melted_gram18_price_irr: float = Field(..., gt=0)


class Black76Request(BaseModel):
    model_config = ConfigDict(extra="forbid")

    F: float = Field(..., gt=0, description="Forward/futures price")
    K: float = Field(..., gt=0, description="Strike price")
    T: float = Field(..., ge=0, description="Time to maturity in years")
    r: float = Field(..., ge=0, description="Risk-free rate (decimal)")
    sigma: float = Field(..., gt=0, description="Volatility (decimal)")
    option_type: str = Field(..., description="call | put")


class ImpliedVolatilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market_price: float = Field(..., gt=0)
    F: float = Field(..., gt=0)
    K: float = Field(..., gt=0)
    T: float = Field(..., gt=0, description="Time to maturity in years (> 0 for IV)")
    r: float = Field(..., ge=0)
    option_type: str = Field(..., description="call | put")


class OptionsChainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    options_chain: list[dict[str, Any]]


class EnrichChainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    options_chain: list[dict[str, Any]]
    forward_price: float = Field(..., gt=0)
    risk_free_rate: float = Field(..., ge=0)
    days_to_expiry: float = Field(..., ge=0)


class FuturesTermRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spot_price: float = Field(..., gt=0)
    contracts: list[dict[str, Any]]
    benchmark_yield: float = Field(
        0.30, description="Decimal; 0.30 = 30%"
    )
    transaction_frictions_pct: float = Field(
        0.01, ge=0, description="Decimal; 0.01 = 1%"
    )


class OptionsStrategyLegRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_type: str | None = Field(None, description="option | underlying")
    option_type: str | None = Field(None, description="call | put")
    strike: float | None = Field(None, gt=0)
    quantity: float = Field(1.0, description="Positive long, negative short")
    premium: float = Field(0.0, ge=0)
    iv: float | None = Field(None, gt=0)
    entry_price: float | None = Field(None, gt=0)


class OptionsStrategyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: str = Field(..., description="straddle | strangle | vertical | iron_condor | covered_call")
    legs: list[OptionsStrategyLegRequest] = Field(..., min_length=1)
    expiry_price: float | None = Field(None, ge=0)
    forward_price: float | None = Field(None, gt=0)
    risk_free_rate: float = Field(0.0, ge=0)
    days_to_expiry: float | None = Field(None, ge=0)
    pre_expiry_days: float | None = Field(None, ge=0)
    pre_expiry_forward: float | None = Field(None, gt=0)


class OptionsMarginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_price: float = Field(..., gt=0)
    prices: list[float] = Field(..., min_length=1)
    direction: int = Field(1, description="1 long, -1 short")
    quantity: float = Field(1.0, gt=0)
    starting_equity: float | None = Field(None, ge=0)
    # STEP 5-FIX-1: ``None`` means "omitted" — the service then falls back to
    # the ``derivatives.margin`` section of config/ime_engine_config.yaml.
    # An explicitly supplied dict overrides the YAML section entirely; keys
    # that are missing (or null in YAML) still yield ``not_configured``.
    config: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Margin assumptions. Omit to use derivatives.margin from the IME "
            "YAML config; an explicit object overrides that section."
        ),
    )


class AedParityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aed_rate: float = Field(..., gt=0)
    tehran_usd_rate: float = Field(..., gt=0)


class MacroPostureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tips_yield: float
    dxy_index: float = Field(..., gt=0)
    gold_trend: str = Field(
        ..., description="up | down | sideways"
    )


class MacroLiveResponse(BaseModel):
    """Gold macro posture evaluated from stored (ingested) data.

    ``available`` is False when required inputs are missing or too stale;
    ``missing`` names which inputs are absent/stale.
    """

    model_config = ConfigDict(extra="forbid")

    available: bool = Field(..., description="Whether posture could be computed")
    missing: list[str] = Field(
        ..., description="Inputs not available or too stale"
    )
    posture: dict[str, Any] | None = Field(
        None, description="Macro posture result when available"
    )
    inputs: dict[str, Any] = Field(
        default_factory=dict, description="Inputs used for the computation"
    )
    tips_staleness_seconds: float | None = Field(
        None, description="Age of the stored TIPS yield in seconds"
    )
    dxy_staleness_seconds: float | None = Field(
        None, description="Age of the stored DXY index in seconds"
    )
    trend_staleness_seconds: float | None = Field(
        None, description="Age of the gold trend derivation in seconds"
    )
    high_vol_window: bool = Field(
        False,
        description=(
            "True when the evaluation date falls inside a CPI/NFP/FOMC "
            "(or Iran manual) high-volatility window"
        ),
    )
    error: str | None = Field(None, description="Computation error, if any")


class MacroCalendarEventResponse(BaseModel):
    """One stored CPI / NFP / FOMC-style calendar event."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(..., description="Stable provider event id")
    event_date: date = Field(..., description="Event date")
    event_time: str | None = Field(None, description="Event time when known")
    title: str | None = Field(None, description="Event title")
    country: str | None = Field(None, description="Country / region")
    category: str | None = Field(None, description="CPI | NFP | FOMC | …")
    importance: int | None = Field(None, description="Provider importance score")
    is_high_volatility: bool = Field(
        False, description="Whether the event opens a high-volatility window"
    )
    source: str | None = Field(None, description="Ingested-from source")


class IranManualEventRequest(BaseModel):
    """Manual entry for an Iran-specific calendar event.

    Iran events have no provider feed, so they are only ever entered by hand.
    """

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(
        ..., min_length=1, max_length=120, description="Caller-supplied stable id"
    )
    event_date: date = Field(..., description="Event date")
    event_time: str | None = Field(None, description="Event time when known")
    title: str | None = Field(None, description="Event title")
    category: str | None = Field(None, description="CPI | NFP | FOMC | FX | …")
    importance: int | None = Field(None, ge=0, le=3, description="0-3 importance")
    note: str | None = Field(None, description="Free-text note")
    is_high_volatility: bool = Field(
        False, description="Whether the event opens a high-volatility window"
    )


class IranManualEventResponse(BaseModel):
    """A stored Iran manual-entry calendar event."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_date: date
    event_time: str | None = None
    title: str | None = None
    category: str | None = None
    importance: int | None = None
    note: str | None = None
    is_high_volatility: bool = False


class GoldSummaryResponse(BaseModel):
    """LIVE summary of gold market.

    All fields optional — null when the provider is missing for that field.
    The ``missing`` list names fields not supplied by any provider.
    """

    model_config = ConfigDict(extra="forbid")

    timestamp: str | None = Field(
        None, description="ISO timestamp of snapshot"
    )
    ounce_usd: float | None = Field(
        None, description="XAU/USD spot price"
    )
    usd_irr: float | None = Field(
        None, description="Free USD rate (IRR per USD)"
    )
    melted_irr: float | None = Field(
        None, description="Melted/th (1 mesghal) price in IRR"
    )
    aed_implied_usd: float | None = Field(
        None, description="AED/USD implied from parity"
    )
    aed_spread_pct: float | None = Field(
        None, description="Spread between aed_implied_usd and AED peg"
    )
    coin_prices: dict[str, float | None] | None = Field(
        None,
        description="Per-coin market prices keyed by coin name (emami, half, quarter, gerami)",
    )
    coin_bubbles: dict[str, dict[str, Any]] | None = Field(
        None, description="Per-coin bubble calculation result"
    )
    missing: list[str] = Field(
        ..., description="Fields not supplied by any provider"
    )



class RiskShockSet(BaseModel):
    """Decimal shocks applied to a gold portfolio scenario."""

    model_config = ConfigDict(extra="forbid")

    xau_usd_pct: float = Field(0.0, gt=-1.0, description="XAU/USD return, 0.10 = +10%")
    usd_irr_pct: float = Field(0.0, gt=-1.0, description="USD/IRR return")
    local_premium_pct: float = Field(0.0, gt=-1.0, description="Coin/futures local premium shock")
    fund_discount_pct: float = Field(0.0, gt=-1.0, description="Fund/ETF NAV discount shock")
    volatility_points: float = Field(0.0, ge=-5.0, le=5.0, description="Implied-vol points, 0.01 = one point")
    liquidity_haircut_pct: float = Field(0.0, ge=0.0, le=1.0, description="Round-trip exit cost")


class RiskScenarioInput(BaseModel):
    """A caller-supplied scenario; omitted names fall back to the id."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(..., min_length=1, max_length=120)
    name_fa: str | None = Field(None, max_length=200)
    name_en: str | None = Field(None, max_length=200)
    description_fa: str | None = Field(None, max_length=1000)
    shocks: RiskShockSet


class RiskPosition(BaseModel):
    """One line of gold exposure in IRR."""

    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(..., min_length=1, max_length=120)
    asset_type: Literal[
        "gold",
        "coin",
        "fund",
        "etf",
        "certificate",
        "futures",
        "option",
        "fx",
        "cash",
        "other",
    ] = "other"
    direction: Literal["long", "short"] = "long"
    exposure_irr: float = Field(..., ge=0)
    delta: float = Field(1.0, ge=-10.0, le=10.0)
    vega_irr_per_vol_point: float = 0.0
    margin_irr: float = Field(0.0, ge=0)
    maintenance_margin_irr: float | None = Field(None, ge=0)


class RiskStressRequest(BaseModel):
    """Inputs for the pure gold stress-test calculator."""

    model_config = ConfigDict(extra="forbid")

    equity_irr: float = Field(..., gt=0)
    positions: list[RiskPosition] = Field(default_factory=list, max_length=500)
    scenarios: list[RiskScenarioInput] | None = Field(None, max_length=50)
__all__ = [
    "AedParityRequest",
    "AssayAdjustmentRequest",
    "Black76Request",
    "CoinBubblesRequest",
    "EnrichChainRequest",
    "FuturesTermRequest",
    "GoldSummaryResponse",
    "ImeArbitrageRequest",
    "ImpliedVolatilityRequest",
    "MacroLiveResponse",
    "MacroPostureRequest",
    "MesghalPriceRequest",
    "OptionsMarginRequest",
    "OptionsChainRequest",
    "OptionsStrategyLegRequest",
    "OptionsStrategyRequest",
    "RiskPosition",
    "RiskScenarioInput",
    "RiskShockSet",
    "RiskStressRequest",
]
