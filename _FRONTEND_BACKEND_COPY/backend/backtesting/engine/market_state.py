from __future__ import annotations

from dataclasses import dataclass

from backtesting.market.market_engine import InstrumentState, MarketEngine


@dataclass(frozen=True)
class MarketSnapshot:
    """Immutable snapshot of a single instrument's market state.

    This is the read-only view that strategies see — they cannot
    mutate market state through this object.
    """

    instrument_id: str
    market_id: str
    best_bid: float
    best_ask: float
    bid_volume: int
    ask_volume: int
    spread: float
    mid_price: float
    last_trade: float
    last_trade_volume: int
    volume: int
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    session_state: str
    price_limit_upper: float
    price_limit_lower: float
    reference_price: float


class MarketState:
    """Read-only market state wrapper for strategies.

    Provides a clean, immutable API for strategies to query market data
    without being able to mutate the underlying engine state.

    Usage:
        state = MarketState(market_engine)
        snapshot = state.of("IRO1FOLD0001")
        if snapshot:
            bid = snapshot.best_bid
            spread = snapshot.spread
    """

    def __init__(self, market_engine: MarketEngine) -> None:
        self._engine = market_engine

    def of(self, instrument_id: str) -> MarketSnapshot | None:
        """Get a snapshot of the current market state for an instrument.

        Returns:
            MarketSnapshot or None if instrument is not tracked
        """
        state = self._engine.get_state(instrument_id)
        if state is None:
            return None
        return self._build_snapshot(state)

    def all(self) -> list[MarketSnapshot]:
        """Get snapshots for all tracked instruments."""
        return [self._build_snapshot(s) for s in self._engine.get_all_states()]

    def instrument_ids(self) -> list[str]:
        """Get list of all tracked instrument IDs."""
        return [s.instrument_id for s in self._engine.get_all_states()]

    @staticmethod
    def _build_snapshot(state: InstrumentState) -> MarketSnapshot:
        bid = state.best_bid
        ask = state.best_ask
        spread = ask - bid if bid > 0 and ask > 0 else 0.0
        mid = (bid + ask) / 2 if bid > 0 and ask > 0 else state.last_trade
        return MarketSnapshot(
            instrument_id=state.instrument_id,
            market_id=state.market_id,
            best_bid=bid,
            best_ask=ask,
            bid_volume=state.bid_volume,
            ask_volume=state.ask_volume,
            spread=spread,
            mid_price=mid,
            last_trade=state.last_trade,
            last_trade_volume=state.last_trade_volume,
            volume=state.volume,
            open_price=state.open_price,
            high_price=state.high_price,
            low_price=state.low_price,
            close_price=state.close_price,
            session_state=state.session_state,
            price_limit_upper=state.price_limit_upper,
            price_limit_lower=state.price_limit_lower,
            reference_price=state.reference_price,
        )
