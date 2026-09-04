"""Pure dataclass contracts for the currency domain.

No I/O. Endpoints and services import from here to type their inputs/outputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

AssetType = Literal["CASH_USD", "USDT"]
SignalType = Literal["BUY", "SELL", "HOLD"]
Confidence = Literal["LOW", "MEDIUM", "HIGH"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]
Sentiment = Literal["BULLISH", "BEARISH", "NEUTRAL"]


@dataclass(frozen=True)
class RatePair:
    """Bid/ask pair with daily move and computed spread."""

    name: str
    source: str
    buy_price: int
    sell_price: int
    daily_change_pct: float

    @property
    def mid_price(self) -> float:
        return (self.buy_price + self.sell_price) / 2.0


@dataclass(frozen=True)
class RateSnapshot:
    """One full market snapshot across all venues."""

    timestamp: datetime
    free: RatePair
    usdt: RatePair
    nima: RatePair
    official_cbi: int  # single rate, no bid/ask


@dataclass(frozen=True)
class MarketSummary:
    free_market_usd: int
    official_cbi_usd: int
    nima_usd: int
    usdt_irt: int
    bubble_index: float
    daily_volatility: float
    bid_ask_spread: float
    tether_arbitrage: float
    sentiment: Sentiment


@dataclass(frozen=True)
class ArbitrageRow:
    name: str
    price: int
    difference_with_free_market: int
    spread_pct: float
    status: Literal["NORMAL", "OPPORTUNITY", "EXPENSIVE"]


@dataclass(frozen=True)
class Signal:
    asset_type: AssetType
    signal_type: SignalType
    confidence: Confidence
    entry_range: tuple[int, int] | None = None
    target_price: int | None = None
    stop_loss: int | None = None
    holding_period: str | None = None
    reason: str = ""
    risk_level: RiskLevel = "MEDIUM"


@dataclass(frozen=True)
class KillSwitch:
    active: bool
    reasons: list[str] = field(default_factory=list)
    action: str | None = None  # "AVOID_NEW_POSITIONS" or None


@dataclass(frozen=True)
class ManualPosition:
    id: int
    user_id: str
    asset_type: AssetType
    entry_price: float
    volume: float
    entry_date: date
    created_at: datetime
    note: str | None = None


@dataclass(frozen=True)
class PositionPnL:
    position: ManualPosition
    current_price: float
    pnl_toman: float
    return_pct: float
