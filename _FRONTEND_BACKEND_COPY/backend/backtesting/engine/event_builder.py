from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class EventType(StrEnum):
    TRADE = "TRADE"
    QUOTE = "QUOTE"
    AUCTION = "AUCTION"
    SESSION_START = "SESSION_START"
    SESSION_END = "SESSION_END"
    STATUS_CHANGE = "STATUS_CHANGE"
    CORPORATE_ACTION = "CORPORATE_ACTION"
    ORDERBOOK_SNAPSHOT = "ORDERBOOK_SNAPSHOT"


@dataclass
class MarketEvent:
    event_id: str
    timestamp: datetime
    instrument_id: str
    market_id: str
    event_type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    priority: int = 0

    def __lt__(self, other: MarketEvent) -> bool:
        if self.timestamp == other.timestamp:
            return self.priority < other.priority
        return self.timestamp < other.timestamp


class EventBuilder:
    def build_trade(
        self,
        event_id: str,
        timestamp: datetime,
        instrument_id: str,
        market_id: str,
        price: float,
        volume: int,
        value: float = 0.0,
    ) -> MarketEvent:
        return MarketEvent(
            event_id=event_id,
            timestamp=timestamp,
            instrument_id=instrument_id,
            market_id=market_id,
            event_type=EventType.TRADE,
            payload={"price": price, "volume": volume, "value": value},
            priority=1,
        )

    def build_quote(
        self,
        event_id: str,
        timestamp: datetime,
        instrument_id: str,
        market_id: str,
        bid: float,
        ask: float,
        bid_volume: int = 0,
        ask_volume: int = 0,
    ) -> MarketEvent:
        return MarketEvent(
            event_id=event_id,
            timestamp=timestamp,
            instrument_id=instrument_id,
            market_id=market_id,
            event_type=EventType.QUOTE,
            payload={"bid": bid, "ask": ask, "bid_volume": bid_volume, "ask_volume": ask_volume},
            priority=2,
        )

    def build_session_event(
        self,
        event_id: str,
        timestamp: datetime,
        instrument_id: str,
        market_id: str,
        event_type: EventType,
    ) -> MarketEvent:
        return MarketEvent(
            event_id=event_id,
            timestamp=timestamp,
            instrument_id=instrument_id,
            market_id=market_id,
            event_type=event_type,
            payload={},
            priority=0,
        )

    def build_auction(
        self,
        event_id: str,
        timestamp: datetime,
        instrument_id: str,
        market_id: str,
        auction_price: float,
        auction_volume: int,
        auction_type: str = "open",
    ) -> MarketEvent:
        return MarketEvent(
            event_id=event_id,
            timestamp=timestamp,
            instrument_id=instrument_id,
            market_id=market_id,
            event_type=EventType.AUCTION,
            payload={"auction_price": auction_price, "auction_volume": auction_volume, "auction_type": auction_type},
            priority=0,
        )

    def build_corporate_action(
        self,
        event_id: str,
        timestamp: datetime,
        instrument_id: str,
        market_id: str,
        action_type: str,
        **kwargs: Any,
    ) -> MarketEvent:
        return MarketEvent(
            event_id=event_id,
            timestamp=timestamp,
            instrument_id=instrument_id,
            market_id=market_id,
            event_type=EventType.CORPORATE_ACTION,
            payload={"action_type": action_type, **kwargs},
            priority=0,
        )

    def from_raw(self, raw: dict[str, Any]) -> MarketEvent:
        event_type = EventType(raw.get("event_type", "TRADE"))
        builder_map = {
            EventType.TRADE: self._from_trade_raw,
            EventType.QUOTE: self._from_quote_raw,
        }
        builder = builder_map.get(event_type, self._from_generic_raw)
        return builder(raw)

    def _from_trade_raw(self, raw: dict[str, Any]) -> MarketEvent:
        return self.build_trade(
            event_id=raw["event_id"],
            timestamp=raw["timestamp"],
            instrument_id=raw["instrument_id"],
            market_id=raw["market_id"],
            price=raw["price"],
            volume=raw["volume"],
            value=raw.get("value", 0.0),
        )

    def _from_quote_raw(self, raw: dict[str, Any]) -> MarketEvent:
        return self.build_quote(
            event_id=raw["event_id"],
            timestamp=raw["timestamp"],
            instrument_id=raw["instrument_id"],
            market_id=raw["market_id"],
            bid=raw["bid"],
            ask=raw["ask"],
            bid_volume=raw.get("bid_volume", 0),
            ask_volume=raw.get("ask_volume", 0),
        )

    def _from_generic_raw(self, raw: dict[str, Any]) -> MarketEvent:
        return MarketEvent(
            event_id=raw["event_id"],
            timestamp=raw["timestamp"],
            instrument_id=raw["instrument_id"],
            market_id=raw["market_id"],
            event_type=EventType(raw.get("event_type", "TRADE")),
            payload=raw.get("payload", {}),
            priority=raw.get("priority", 5),
        )
