"""Data Contracts — v5.0 Data Plane — Raw_Tick, Signal_Candidate, Trade_Card, Execution_Feedback."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class DataQuality(str, Enum):
    OK = "OK"
    DEGRADED = "DEGRADED"


class Source(str, Enum):
    BRSAPI = "BrsApi"
    IME_FALLBACK = "IME_Fallback"


class MaturityLevel(str, Enum):
    ALERT = "1_Alert"  # Data Alert
    OPPORTUNITY = "2_Opportunity"  # Analytical Opportunity
    TRADE_CARD = "3_TradeCard"  # Actionable Trade Card


class StrategyType(str, Enum):
    IV_MEAN_REVERSION = "IV_MeanReversion"
    CALENDAR_ARB = "CalendarArb"
    GAMMA_SCALP = "GammaScalp"


class TradeCardStatus(str, Enum):
    ISSUED = "ISSUED"
    EXPIRED = "EXPIRED"
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"


class RejectionReason(str, Enum):
    DATA_STALE = "REJECTED_DATA_STALE"
    DELIVERY_RISK = "REJECTED_DELIVERY_RISK"
    LOW_LIQUIDITY = "REJECTED_LOW_LIQUIDITY"
    TICK_MISMATCH = "REJECTED_TICK_MISMATCH"
    COST_NOT_COVERED = "REJECTED_COST_NOT_COVERED"
    MODEL_LOW_CONFIDENCE = "REJECTED_MODEL_LOW_CONFIDENCE"


# ── Instrument Key (سند §3.3) ──
@dataclass(frozen=True)
class InstrumentKey:
    symbol_id: str
    underlying_asset: str
    contract_type: str  # option/future/certificate/physical
    strike_price: float | None = None
    expiry_date: str | None = None  # YYYY-MM-DD
    contract_size: int = 1000
    delivery_location: str | None = None

    def __str__(self) -> str:
        parts = [self.symbol_id, self.underlying_asset, self.contract_type]
        if self.strike_price is not None:
            parts.append(f"K{self.strike_price:g}")
        if self.expiry_date:
            parts.append(self.expiry_date)
        return "|".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol_id": self.symbol_id,
            "underlying_asset": self.underlying_asset,
            "contract_type": self.contract_type,
            "strike_price": self.strike_price,
            "expiry_date": self.expiry_date,
            "contract_size": self.contract_size,
            "delivery_location": self.delivery_location,
        }


# ── Raw Tick (سند §7.1) ──
@dataclass
class RawTick:
    instrument_key: str  # InstrumentKey.__str__
    market_time: datetime
    receive_time: datetime
    best_bid: float | None
    best_ask: float | None
    volume_visible: int | None = None
    open_interest: int | None = None
    source: Source = Source.BRSAPI
    data_quality: DataQuality = DataQuality.OK
    checksum_sha256: str = ""
    schema_version: str = "raw_tick.v1"

    def compute_checksum(self) -> str:
        canonical = json.dumps(
            {
                "instrument_key": self.instrument_key,
                "market_time": self.market_time.isoformat(),
                "best_bid": self.best_bid,
                "best_ask": self.best_ask,
            },
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    def mid_price(self) -> float | None:
        """Guard Clause: اگر Bid/Ask نامعتبر، Mid نامعتبر است."""
        if self.best_bid is None or self.best_ask is None:
            return None
        if self.best_bid <= 0 or self.best_ask <= 0 or self.best_ask < self.best_bid:
            return None
        return (self.best_bid + self.best_ask) / 2.0

    def is_stale(self, now: datetime, max_age_sec: int = 60) -> bool:
        return (now - self.receive_time).total_seconds() > max_age_sec


# ── Signal Candidate (سند §7.2) ──
@dataclass
class Greeks:
    delta: float
    gamma: float
    theta: float
    vega: float


@dataclass
class SignalCandidate:
    candidate_id: str = field(default_factory=lambda: str(uuid4()))
    strategy_type: StrategyType = StrategyType.IV_MEAN_REVERSION
    instrument_keys: list[str] = field(default_factory=list)
    theoretical_price: float = 0.0
    market_price: float = 0.0
    mispricing_pct: float = 0.0
    iv: float | None = None
    greeks: Greeks | None = None
    model_version: str = "black76.v1"
    calculation_version: str = "calc.v1"
    input_data_timestamp: datetime = field(default_factory=datetime.utcnow)
    maturity_level: MaturityLevel = MaturityLevel.ALERT

    def promote(self) -> MaturityLevel:
        if self.maturity_level == MaturityLevel.ALERT:
            self.maturity_level = MaturityLevel.OPPORTUNITY
        elif self.maturity_level == MaturityLevel.OPPORTUNITY:
            self.maturity_level = MaturityLevel.TRADE_CARD
        return self.maturity_level


# ── Trade Card (سند §7.3) ──
@dataclass
class TradeLeg:
    instrument_key: str
    direction: str  # Buy/Sell
    quantity: int
    limit_price: float
    execution_order: int = 1


@dataclass
class TradeCard:
    card_id: str = field(default_factory=lambda: str(uuid4()))
    candidate_id: str = ""
    legs: list[TradeLeg] = field(default_factory=list)
    net_edge: float = 0.0
    signal_score: float = 0.0  # 0.30*DQ + 0.25*Liq + 0.25*Exec + 0.20*Model
    position_size_suggested: int = 0
    invalidation_point: float = 0.0
    max_loss: float = 0.0
    ttl_seconds: int = 300
    issued_at: datetime = field(default_factory=datetime.utcnow)
    status: TradeCardStatus = TradeCardStatus.ISSUED
    rejection_reason: RejectionReason | None = None

    def is_expired(self, now: datetime) -> bool:
        return (now - self.issued_at).total_seconds() > self.ttl_seconds


# ── Execution Feedback (سند §7.4) ──
@dataclass
class ExecutionFeedback:
    card_id: str
    leg_index: int
    actual_fill_price: float
    actual_fill_quantity: int
    broker_order_timestamp: datetime
    reported_by_user_id: str
    reported_at: datetime = field(default_factory=datetime.utcnow)
