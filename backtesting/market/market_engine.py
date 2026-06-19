from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backtesting.market.rule_engine import MarketRuleEngine
from backtesting.types import OrderEvent
from domain.markets.enums import MarketStatus


@dataclass
class InstrumentState:
    instrument_id: str
    market_id: str
    best_bid: float = 0.0
    best_ask: float = 0.0
    bid_volume: int = 0
    ask_volume: int = 0
    last_trade: float = 0.0
    last_trade_volume: int = 0
    open_price: float = 0.0
    close_price: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    volume: int = 0
    value: float = 0.0
    queue_state: str = "idle"
    session_state: str = "closed"
    price_limit_upper: float = 0.0
    price_limit_lower: float = 0.0
    reference_price: float = 0.0
    status: MarketStatus = MarketStatus.CLOSED
    extra: dict[str, Any] = field(default_factory=dict)


class MarketEngine:
    def __init__(self, rule_engine: MarketRuleEngine | None = None) -> None:
        self._rule_engine = rule_engine or MarketRuleEngine()
        self._instruments: dict[str, InstrumentState] = {}
        self._listeners: list[Any] = []

    def add_instrument(self, instrument_id: str, market_id: str, reference_price: float = 0.0) -> InstrumentState:
        state = InstrumentState(
            instrument_id=instrument_id,
            market_id=market_id,
            reference_price=reference_price,
        )
        self._instruments[instrument_id] = state
        return state

    def get_state(self, instrument_id: str) -> InstrumentState | None:
        return self._instruments.get(instrument_id)

    def get_all_states(self) -> list[InstrumentState]:
        return list(self._instruments.values())

    def update_quote(
        self,
        instrument_id: str,
        bid: float = 0.0,
        ask: float = 0.0,
        bid_vol: int = 0,
        ask_vol: int = 0,
    ) -> None:
        state = self._instruments.get(instrument_id)
        if state is None:
            return
        state.best_bid = bid
        state.best_ask = ask
        state.bid_volume = bid_vol
        state.ask_volume = ask_vol

    def update_trade(
        self,
        instrument_id: str,
        price: float,
        volume: int,
        value: float = 0.0,
    ) -> None:
        state = self._instruments.get(instrument_id)
        if state is None:
            return
        state.last_trade = price
        state.last_trade_volume = volume
        if value > 0:
            state.value = value
        state.volume += volume
        if state.high_price == 0 or price > state.high_price:
            state.high_price = price
        if state.low_price == 0 or price < state.low_price:
            state.low_price = price

    def set_session_state(self, instrument_id: str, session: str, status: MarketStatus) -> None:
        state = self._instruments.get(instrument_id)
        if state is None:
            return
        state.session_state = session
        state.status = status

    def update_price_limits(self, instrument_id: str) -> None:
        state = self._instruments.get(instrument_id)
        if state is None or state.reference_price <= 0:
            return
        rules = self._rule_engine.get_rules(state.market_id)
        change = state.reference_price * (rules.price_limit.max_change_pct / 100.0)
        state.price_limit_upper = state.reference_price + change
        state.price_limit_lower = max(0, state.reference_price - change)

    def check_order(self, order: OrderEvent) -> tuple[bool, str]:
        state = self._instruments.get(order.instrument_id)
        if state is None:
            return False, f"Instrument {order.instrument_id} not tracked"
        return self._rule_engine.validate_order(state.market_id, order)

    def on(self, event_type: str, listener: Any) -> None:
        self._listeners.append((event_type, listener))

    def _emit(self, event_type: str, data: Any) -> None:
        for et, listener in self._listeners:
            if et == event_type:
                listener(data)

    def reset(self) -> None:
        self._instruments.clear()
