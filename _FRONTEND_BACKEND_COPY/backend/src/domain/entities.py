from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class MarketBar:
    """Canonical market bar — واحد استاندارد داخلی (UTC، بدون وابستگی به منبع)."""

    symbol: str  # gold_18k, usd_irr_free, xau_usd
    timestamp_utc: datetime
    timeframe: str  # 1d, 1h, 1m
    close: Decimal
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    volume: Decimal | None = None
    currency: str = "IRR"
    source: str = "brsapi"
    quality_status: str = "valid"  # valid | suspicious | quarantined


@dataclass(frozen=True, slots=True)
class ForecastPoint:
    date: str  # YYYY-MM-DD
    p50: int
    p_lower: int
    p_upper: int
    direction_probability_up: float
