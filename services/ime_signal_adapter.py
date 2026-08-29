"""IME / Option signal adapter — bridges MultiMarketSignalEngine with the IME signal factory.

سند v5.0 §4 + §20.2: connects the rule-based signal generation
(MultiMarketSignalEngine) to the IME Hard-Block / Trade-Card pipeline so that
option and IME signals go through the same:
  1. Six hard blocks (REJECTED_DATA_STALE / DELIVERY_RISK / LOW_LIQUIDITY /
     TICK_MISMATCH / COST_NOT_COVERED / MODEL_LOW_CONFIDENCE)
  2. NetEdge cost model (Almgren-Chriss slippage)
  3. Signal_Score → tier → Fixed Fractional sizing
  4. Trade Card dataclass with TTL, legs, score, status

Adapters exist only for ``option`` and ``ime`` markets — the other markets
(stock / gold / etc.) keep their legacy flow. The adapter is intentionally
side-effect free: it maps dataclasses to dataclasses without touching the
DB; persistence is the caller's job.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from services.ime_signal_factory import (
    MarketState,
    PricingCandidate,
    RejectCode,
    SignalMaturity,
    StrategyType,
    TradeCard,
    process_candidate,
)

logger = logging.getLogger(__name__)

# Only option / ime markets flow through the IME factory
IME_MARKETS = frozenset({"option", "ime"})

# Map MarketSignal.direction to StrategyType
_STRATEGY_FROM_DIRECTION = {
    "buy": StrategyType.IV_MEAN_REVERSION,  # most common for these markets
    "sell": StrategyType.IV_MEAN_REVERSION,
}


def _parse_persian_number(s: str | float | int | None) -> float | None:
    """Parse Persian-formatted numbers like '۹۷۵,۰۰۰' or '975000' to float.

    Returns None when the string is empty, None, or unparseable.
    """
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip()
    if not s:
        return None
    # Convert Persian digits
    persian = "۰۱۲۳۴۵۶۷۸۹"
    ascii = "0123456789"
    for p, a in zip(persian, ascii, strict=False):
        s = s.replace(p, a)
    # Strip units, parentheses, percent signs
    s = s.replace(",", "").replace("،", "")
    s = re.sub(r"[\(\)٪%]", "", s)
    # Keep only digits, dot, and minus
    s = re.sub(r"[^\d\.\-]", "", s)
    if not s or s in (".", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _infer_strategy_type(market: str, direction: str) -> StrategyType:
    """Pick the StrategyType enum value from the market + direction.

    IME futures default to calendar-arb style; options default to IV mean
    reversion. A more sophisticated mapping could inspect the
    MarketSignal.source field, but for now this keeps the wiring simple
    and traceable.
    """
    if market == "ime":
        return StrategyType.CALENDAR_ARB
    return _STRATEGY_FROM_DIRECTION.get(direction, StrategyType.IV_MEAN_REVERSION)


def _build_market_state(signal: Any) -> MarketState:
    """Convert a MarketSignal into a MarketState for the IME factory.

    Best-effort mapping — fields that cannot be inferred (e.g. days_to_delivery)
    fall back to safe defaults so the Hard Blocks produce sensible results.
    """
    entry_price = signal.price or _parse_persian_number(signal.entry_zone) or 0.0
    stop_loss_pct = 0.02  # default 2% stop
    if signal.stop_loss:
        sl = _parse_persian_number(signal.stop_loss)
        if sl and entry_price:
            stop_loss_pct = abs(entry_price - sl) / entry_price
    return MarketState(
        snapshot_age_seconds=0.0,  # live; consumer must override if stale
        days_to_delivery=30.0,  # default; consumer can refine
        delivery_capability_checked=False,
        visible_volume=1000,  # placeholder; consumer can refine
        min_strategy_volume=100,
        tick_size=_infer_tick_size(entry_price),
        proposed_price=entry_price,
        data_degraded=False,
        iv_converged=True,
        calibration_rmse=0.01,
        gross_edge=_infer_gross_edge(signal, entry_price),
        commission=0.001 * entry_price,  # 0.1% commission estimate
        market_impact=0.0,
        latency_buffer=0.0005 * entry_price,
        avg_volume=5000,
        short_term_volatility=0.25,  # default short-term vol
        eta=0.1,
        gamma=0.05,
        account_risk_budget=10_000_000.0,
        stop_loss_distance=max(stop_loss_pct * entry_price, 1.0),
    )


def _infer_tick_size(price: float) -> float:
    """Infer Iranian market tick size from price magnitude.

    Heuristic: high-value assets (gold, options) have 1000-rial ticks;
    lower-value ones use 100-rial or 1-rial ticks. The exact value is set
    by the exchange per instrument; this is a best-effort default that
    makes the tick-mismatch block reject only truly off-grid prices.
    """
    if price <= 0:
        return 1.0
    if price > 10_000_000:
        return 10_000.0
    if price > 1_000_000:
        return 1_000.0
    if price > 10_000:
        return 100.0
    return 1.0


def _infer_gross_edge(signal: Any, entry_price: float) -> float:
    """Approximate gross edge in price units from confidence × entry.

    The actual gross edge depends on target/stop which is in Persian strings;
    we use signal.confidence (0-1) × entry_price as a heuristic. The Hard
    Block for COST_NOT_COVERED will reject candidates where this isn't
    realistic.
    """
    if not entry_price:
        return 0.0
    return signal.confidence * entry_price * 0.05  # 5% of entry * confidence


def market_signal_to_candidate(signal: Any) -> PricingCandidate:
    """Convert a ``MarketSignal`` into a ``PricingCandidate`` (سند §20.2)."""
    instrument_keys = [signal.symbol]
    if signal.market and signal.name:
        instrument_keys.append(f"{signal.market}:{signal.name}")
    return PricingCandidate(
        candidate_id=str(uuid.uuid4()),
        strategy_type=_infer_strategy_type(signal.market, signal.direction),
        instrument_keys=instrument_keys,
        theoretical_price=None,
        market_price=signal.price if signal.price else None,
        mispricing_pct=None,
        iv=None,
        model_version="ime-signal-adapter-v1",
        calculation_version="ime-signal-adapter-v1",
        input_data_timestamp=datetime.now(UTC),
        data_quality=min(1.0, signal.confidence * 1.2) if signal.confidence else 0.5,
        liquidity_depth=min(1.0, signal.strength) if signal.strength else 0.5,
        execution_ease=min(1.0, signal.confidence * 0.9 + 0.1) if signal.confidence else 0.5,
        model_confidence=signal.confidence if signal.confidence else 0.0,
    )


@dataclass
class AdapterResult:
    market: str
    symbol: str
    maturity: SignalMaturity
    reject_code: RejectCode | None
    trade_card: TradeCard | None = None
    rejection_reason: str | None = None

    @property
    def is_releasable(self) -> bool:
        return self.maturity is SignalMaturity.TRADE_CARD and self.trade_card is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "market": self.market,
            "symbol": self.symbol,
            "maturity": self.maturity.name,
            "reject_code": self.reject_code.value if self.reject_code else None,
            "trade_card": self.trade_card.to_dict() if self.trade_card else None,
            "rejection_reason": self.rejection_reason,
            "is_releasable": self.is_releasable,
        }


async def convert_signal(signal: Any, ttl_seconds: int = 20) -> AdapterResult:
    """Run one MarketSignal through the IME factory.

    Returns an ``AdapterResult`` with the verdict and (if released) the
    Trade Card. Errors from the factory are caught and surfaced as
    ``DATA_ALERT`` with a synthetic ``REJECTED_DATA_STALE`` code so the
    caller can log without breaking the broader pipeline.
    """
    from services.kill_switch import TradingHaltedError

    if signal.market not in IME_MARKETS:
        return AdapterResult(
            market=signal.market,
            symbol=signal.symbol,
            maturity=SignalMaturity.DATA_ALERT,
            reject_code=RejectCode.REJECTED_DATA_STALE,
            rejection_reason=f"market {signal.market!r} not in IME flow",
        )

    try:
        candidate = market_signal_to_candidate(signal)
        state = _build_market_state(signal)
        maturity, reject, card = process_candidate(candidate, state, ttl_seconds=ttl_seconds)
        return AdapterResult(
            market=signal.market,
            symbol=signal.symbol,
            maturity=maturity,
            reject_code=reject,
            trade_card=card,
        )
    except TradingHaltedError as exc:
        logger.warning("convert_signal: kill switch active, refusing %s/%s", signal.market, signal.symbol)
        return AdapterResult(
            market=signal.market,
            symbol=signal.symbol,
            maturity=SignalMaturity.DATA_ALERT,
            reject_code=RejectCode.REJECTED_DATA_STALE,
            rejection_reason=f"kill switch: {exc}",
        )
    except Exception as exc:  # last-resort: never let a bad signal break the loop
        logger.exception("convert_signal: unexpected error for %s/%s", signal.market, signal.symbol)
        return AdapterResult(
            market=signal.market,
            symbol=signal.symbol,
            maturity=SignalMaturity.DATA_ALERT,
            reject_code=RejectCode.REJECTED_DATA_STALE,
            rejection_reason=f"adapter error: {type(exc).__name__}: {exc}",
        )


async def convert_signals(signals: list[Any], ttl_seconds: int = 20) -> list[AdapterResult]:
    """Convert a batch of signals sequentially (order matters for some
    downstream consumers that index by position).
    """
    return [await convert_signal(s, ttl_seconds) for s in signals]


def filter_ime_market_signals(signals: list[Any]) -> list[Any]:
    """Pick out the option / ime signals from a multi-market batch."""
    return [s for s in signals if getattr(s, "market", "") in IME_MARKETS]


def _trade_card_to_dict(self) -> dict[str, Any]:
    """JSON-friendly view of a TradeCard (سند §20.3)."""
    return {
        "card_id": self.card_id,
        "candidate_id": self.candidate_id,
        "legs": [
            {
                "instrument_key": leg.instrument_key,
                "direction": leg.direction,
                "quantity": leg.quantity,
                "limit_price": leg.limit_price,
                "execution_order": leg.execution_order,
            }
            for leg in self.legs
        ],
        "net_edge": self.net_edge,
        "signal_score": self.signal_score,
        "position_size_suggested": self.position_size_suggested,
        "invalidation_point": self.invalidation_point,
        "max_loss": self.max_loss,
        "ttl_seconds": self.ttl_seconds,
        "issued_at": self.issued_at.isoformat() if self.issued_at else None,
        "status": self.status,
        "rejection_reason": self.rejection_reason,
    }


# Attach once at import time. idempotent.
if not hasattr(TradeCard, "to_dict"):
    TradeCard.to_dict = _trade_card_to_dict  # type: ignore[attr-defined]
