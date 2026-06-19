from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class MarketType(StrEnum):
    TSE = "tse"             # Tehran Stock Exchange (queue-based)
    CRYPTO = "crypto"       # Cryptocurrency (full orderbook)
    FUTURES = "futures"     # Futures (margin + funding)
    OPTIONS = "options"     # Options (greeks)
    FOREX = "forex"         # Forex (OTC)
    COMMODITY = "commodity" # Commodity (auction-based)
    FIXED_INCOME = "fixed_income" # Bonds


@dataclass
class UnifiedEvent:
    """Unified event format that all market adapters produce."""
    timestamp: datetime
    market_id: str
    market_type: MarketType
    instrument_id: str
    event_type: str  # TRADE, QUOTE, ORDERBOOK, FUNDING, LIQUIDATION
    price: float = 0.0
    volume: int = 0
    side: str = ""
    bid: float = 0.0
    ask: float = 0.0
    bid_volume: int = 0
    ask_volume: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class MarketAdapter(ABC):
    """Abstract base for all market adapters.

    Each adapter normalizes market-specific data into UnifiedEvent format.
    """

    @abstractmethod
    def normalize_trade(self, raw: dict[str, Any]) -> UnifiedEvent: ...

    @abstractmethod
    def normalize_quote(self, raw: dict[str, Any]) -> UnifiedEvent: ...

    @abstractmethod
    def normalize_orderbook(self, raw: dict[str, Any]) -> UnifiedEvent: ...

    @abstractmethod
    def normalize_execution_rules(self) -> dict[str, Any]: ...


class TSEAdapter(MarketAdapter):
    """Adapter for Tehran Stock Exchange (queue-based, price-limited)."""

    def normalize_trade(self, raw: dict[str, Any]) -> UnifiedEvent:
        return UnifiedEvent(
            timestamp=raw.get("timestamp", datetime.now()),
            market_id="tse",
            market_type=MarketType.TSE,
            instrument_id=raw.get("instrument_id", ""),
            event_type="TRADE",
            price=raw.get("price", 0.0),
            volume=raw.get("volume", 0),
            side=raw.get("side", "buy"),
            metadata={"queue_volume": raw.get("queue_volume", 0), "price_limit_pct": 5.0},
        )

    def normalize_quote(self, raw: dict[str, Any]) -> UnifiedEvent:
        return UnifiedEvent(
            timestamp=raw.get("timestamp", datetime.now()),
            market_id="tse",
            market_type=MarketType.TSE,
            instrument_id=raw.get("instrument_id", ""),
            event_type="QUOTE",
            bid=raw.get("bid", 0.0),
            ask=raw.get("ask", 0.0),
            bid_volume=raw.get("bid_volume", 0),
            ask_volume=raw.get("ask_volume", 0),
            metadata={"queue_state": raw.get("queue_state", "idle")},
        )

    def normalize_orderbook(self, raw: dict[str, Any]) -> UnifiedEvent:
        return self.normalize_quote(raw)

    def normalize_execution_rules(self) -> dict[str, Any]:
        return {"price_limit_pct": 5.0, "has_queue": True, "has_auction": True, "has_market_order": True, "settlement": "T+2"}


class CryptoAdapter(MarketAdapter):
    """Adapter for cryptocurrency exchanges (full orderbook, 24/7)."""

    def normalize_trade(self, raw: dict[str, Any]) -> UnifiedEvent:
        return UnifiedEvent(
            timestamp=raw.get("timestamp", datetime.now()),
            market_id=raw.get("exchange", "crypto"),
            market_type=MarketType.CRYPTO,
            instrument_id=raw.get("symbol", ""),
            event_type="TRADE",
            price=raw.get("price", 0.0),
            volume=raw.get("volume", 0),
            side=raw.get("side", "buy"),
            metadata={"exchange": raw.get("exchange", ""), "trade_id": raw.get("trade_id", "")},
        )

    def normalize_quote(self, raw: dict[str, Any]) -> UnifiedEvent:
        return UnifiedEvent(
            timestamp=raw.get("timestamp", datetime.now()),
            market_id=raw.get("exchange", "crypto"),
            market_type=MarketType.CRYPTO,
            instrument_id=raw.get("symbol", ""),
            event_type="QUOTE",
            bid=raw.get("bid", 0.0),
            ask=raw.get("ask", 0.0),
            bid_volume=raw.get("bid_volume", 0),
            ask_volume=raw.get("ask_volume", 0),
        )

    def normalize_orderbook(self, raw: dict[str, Any]) -> UnifiedEvent:
        return UnifiedEvent(
            timestamp=raw.get("timestamp", datetime.now()),
            market_id=raw.get("exchange", "crypto"),
            market_type=MarketType.CRYPTO,
            instrument_id=raw.get("symbol", ""),
            event_type="ORDERBOOK",
            bid=raw.get("bid", 0.0),
            ask=raw.get("ask", 0.0),
            metadata={"bids": raw.get("bids", []), "asks": raw.get("asks", [])},
        )

    def normalize_execution_rules(self) -> dict[str, Any]:
        return {"trading_24_7": True, "has_full_orderbook": True, "has_funding": True, "has_leverage": True, "settlement": "instant"}


class FuturesAdapter(MarketAdapter):
    """Adapter for futures/derivatives exchanges."""

    def normalize_trade(self, raw: dict[str, Any]) -> UnifiedEvent:
        return UnifiedEvent(
            timestamp=raw.get("timestamp", datetime.now()),
            market_id=raw.get("exchange", "futures"),
            market_type=MarketType.FUTURES,
            instrument_id=raw.get("contract", ""),
            event_type="TRADE",
            price=raw.get("price", 0.0),
            volume=raw.get("volume", 0),
            side=raw.get("side", "buy"),
            metadata={
                "expiry": raw.get("expiry", ""),
                "open_interest": raw.get("open_interest", 0),
                "funding_rate": raw.get("funding_rate", 0.0),
            },
        )

    def normalize_quote(self, raw: dict[str, Any]) -> UnifiedEvent:
        return UnifiedEvent(
            timestamp=raw.get("timestamp", datetime.now()),
            market_id=raw.get("exchange", "futures"),
            market_type=MarketType.FUTURES,
            instrument_id=raw.get("contract", ""),
            event_type="QUOTE",
            bid=raw.get("bid", 0.0),
            ask=raw.get("ask", 0.0),
            bid_volume=raw.get("bid_volume", 0),
            ask_volume=raw.get("ask_volume", 0),
            metadata={"mark_price": raw.get("mark_price", 0.0), "funding_rate": raw.get("funding_rate", 0.0)},
        )

    def normalize_orderbook(self, raw: dict[str, Any]) -> UnifiedEvent:
        return self.normalize_quote(raw)

    def normalize_execution_rules(self) -> dict[str, Any]:
        return {"margin_required": True, "daily_settlement": True, "has_funding": True, "has_leverage": True, "expiry": "contract_specific"}


class OptionsAdapter(MarketAdapter):
    """Adapter for options markets."""

    def normalize_trade(self, raw: dict[str, Any]) -> UnifiedEvent:
        return UnifiedEvent(
            timestamp=raw.get("timestamp", datetime.now()),
            market_id=raw.get("exchange", "options"),
            market_type=MarketType.OPTIONS,
            instrument_id=raw.get("option_symbol", ""),
            event_type="TRADE",
            price=raw.get("premium", 0.0),
            volume=raw.get("volume", 0),
            side=raw.get("side", "buy"),
            metadata={
                "strike": raw.get("strike", 0),
                "expiry": raw.get("expiry", ""),
                "option_type": raw.get("option_type", "call"),
                "iv": raw.get("implied_volatility", 0.0),
                "delta": raw.get("delta", 0.0),
                "gamma": raw.get("gamma", 0.0),
                "theta": raw.get("theta", 0.0),
                "vega": raw.get("vega", 0.0),
            },
        )

    def normalize_quote(self, raw: dict[str, Any]) -> UnifiedEvent:
        return UnifiedEvent(
            timestamp=raw.get("timestamp", datetime.now()),
            market_id=raw.get("exchange", "options"),
            market_type=MarketType.OPTIONS,
            instrument_id=raw.get("option_symbol", ""),
            event_type="QUOTE",
            bid=raw.get("bid", 0.0),
            ask=raw.get("ask", 0.0),
            bid_volume=raw.get("bid_volume", 0),
            ask_volume=raw.get("ask_volume", 0),
            metadata={"iv_bid": raw.get("iv_bid", 0.0), "iv_ask": raw.get("iv_ask", 0.0)},
        )

    def normalize_orderbook(self, raw: dict[str, Any]) -> UnifiedEvent:
        return self.normalize_quote(raw)

    def normalize_execution_rules(self) -> dict[str, Any]:
        return {"has_greeks": True, "has_expiry": True, "has_iv": True, "exercise_style": "both"}


class ForexAdapter(MarketAdapter):
    """Adapter for Forex (OTC) markets."""

    def normalize_trade(self, raw: dict[str, Any]) -> UnifiedEvent:
        return UnifiedEvent(
            timestamp=raw.get("timestamp", datetime.now()),
            market_id=raw.get("broker", "forex"),
            market_type=MarketType.FOREX,
            instrument_id=raw.get("pair", ""),
            event_type="TRADE",
            price=raw.get("price", 0.0),
            volume=raw.get("volume", 0),
            side=raw.get("side", "buy"),
            metadata={"broker": raw.get("broker", ""), "spread_raw": raw.get("spread", 0.0)},
        )

    def normalize_quote(self, raw: dict[str, Any]) -> UnifiedEvent:
        return UnifiedEvent(
            timestamp=raw.get("timestamp", datetime.now()),
            market_id=raw.get("broker", "forex"),
            market_type=MarketType.FOREX,
            instrument_id=raw.get("pair", ""),
            event_type="QUOTE",
            bid=raw.get("bid", 0.0),
            ask=raw.get("ask", 0.0),
            bid_volume=raw.get("bid_volume", 0),
            ask_volume=raw.get("ask_volume", 0),
        )

    def normalize_orderbook(self, raw: dict[str, Any]) -> UnifiedEvent:
        return self.normalize_quote(raw)

    def normalize_execution_rules(self) -> dict[str, Any]:
        return {"is_otc": True, "has_spread_only": True, "trading_24_5": True, "has_leverage": True, "settlement": "T+2"}


class MarketAdapterFactory:
    """Factory for creating market adapters by type."""

    @staticmethod
    def create(market_type: MarketType | str) -> MarketAdapter:
        if isinstance(market_type, str):
            market_type = MarketType(market_type)

        adapters = {
            MarketType.TSE: TSEAdapter(),
            MarketType.CRYPTO: CryptoAdapter(),
            MarketType.FUTURES: FuturesAdapter(),
            MarketType.OPTIONS: OptionsAdapter(),
            MarketType.FOREX: ForexAdapter(),
        }
        adapter = adapters.get(market_type)
        if adapter is None:
            msg = f"Unsupported market type: {market_type}"
            raise ValueError(msg)
        return adapter
