from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from core.time import now_tehran


class MarketType(StrEnum):
    TSE = "tse"             # Tehran Stock Exchange (queue-based)
    CRYPTO = "crypto"       # Cryptocurrency (full orderbook)
    FUTURES = "futures"     # Futures (margin + funding)
    OPTIONS = "options"     # Options (greeks)
    FOREX = "forex"         # Forex (OTC)
    COMMODITY = "commodity" # Commodity (auction-based)
    FIXED_INCOME = "fixed_income" # Bonds
    SUKUK = "sukuk"         # Islamic fixed income (coupon + accrued interest)
    FX_FUTURES = "fx_futures"     # Currency futures (margin + expiry)
    AGRICULTURAL = "agricultural" # IME agricultural commodities (physical delivery)


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
            timestamp=raw.get("timestamp", now_tehran()),
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
            timestamp=raw.get("timestamp", now_tehran()),
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
            timestamp=raw.get("timestamp", now_tehran()),
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
            timestamp=raw.get("timestamp", now_tehran()),
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
            timestamp=raw.get("timestamp", now_tehran()),
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
            timestamp=raw.get("timestamp", now_tehran()),
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
            timestamp=raw.get("timestamp", now_tehran()),
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
            timestamp=raw.get("timestamp", now_tehran()),
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
            timestamp=raw.get("timestamp", now_tehran()),
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
            timestamp=raw.get("timestamp", now_tehran()),
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
            timestamp=raw.get("timestamp", now_tehran()),
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


class SukukAdapter(MarketAdapter):
    """Adapter for sukuk / fixed-income instruments (clean price + accrued interest)."""

    market_type: MarketType = MarketType.SUKUK
    default_market_id = "sukuk"

    def normalize_trade(self, raw: dict[str, Any]) -> UnifiedEvent:
        return UnifiedEvent(
            timestamp=raw.get("timestamp", now_tehran()),
            market_id=raw.get("exchange", self.default_market_id),
            market_type=self.market_type,
            instrument_id=raw.get("instrument_id", raw.get("symbol", "")),
            event_type="TRADE",
            price=raw.get("price", 0.0),
            volume=raw.get("volume", 0),
            side=raw.get("side", "buy"),
            metadata={
                "coupon_rate": raw.get("coupon_rate", 0.0),
                "accrued_interest": raw.get("accrued_interest", 0.0),
                "yield_to_maturity": raw.get("yield_to_maturity", 0.0),
                "maturity_date": raw.get("maturity_date", ""),
            },
        )

    def normalize_quote(self, raw: dict[str, Any]) -> UnifiedEvent:
        return UnifiedEvent(
            timestamp=raw.get("timestamp", now_tehran()),
            market_id=raw.get("exchange", self.default_market_id),
            market_type=self.market_type,
            instrument_id=raw.get("instrument_id", raw.get("symbol", "")),
            event_type="QUOTE",
            bid=raw.get("bid", 0.0),
            ask=raw.get("ask", 0.0),
            bid_volume=raw.get("bid_volume", 0),
            ask_volume=raw.get("ask_volume", 0),
            metadata={
                "clean_price": raw.get("clean_price", 0.0),
                "dirty_price": raw.get("dirty_price", 0.0),
                "accrued_interest": raw.get("accrued_interest", 0.0),
            },
        )

    def normalize_orderbook(self, raw: dict[str, Any]) -> UnifiedEvent:
        return self.normalize_quote(raw)

    def normalize_execution_rules(self) -> dict[str, Any]:
        return {
            "fixed_income": True,
            "quote_basis": "clean_price",
            "accrues_interest": True,
            "has_queue": True,
            "price_limit": "board_specific",
            "settlement": "T+2",
        }


class FixedIncomeAdapter(SukukAdapter):
    """Adapter for conventional fixed-income bonds."""

    market_type = MarketType.FIXED_INCOME
    default_market_id = "fixed_income"


class CommodityAdapter(MarketAdapter):
    """Adapter for exchange-traded commodities (IME, auction-based)."""

    market_type: MarketType = MarketType.COMMODITY
    default_market_id = "ime"

    def normalize_trade(self, raw: dict[str, Any]) -> UnifiedEvent:
        return UnifiedEvent(
            timestamp=raw.get("timestamp", now_tehran()),
            market_id=raw.get("exchange", self.default_market_id),
            market_type=self.market_type,
            instrument_id=raw.get("contract", raw.get("symbol", "")),
            event_type="TRADE",
            price=raw.get("price", 0.0),
            volume=raw.get("volume", 0),
            side=raw.get("side", "buy"),
            metadata={
                "commodity": raw.get("commodity", ""),
                "grade": raw.get("grade", ""),
                "delivery_month": raw.get("delivery_month", ""),
                "open_interest": raw.get("open_interest", 0),
            },
        )

    def normalize_quote(self, raw: dict[str, Any]) -> UnifiedEvent:
        return UnifiedEvent(
            timestamp=raw.get("timestamp", now_tehran()),
            market_id=raw.get("exchange", self.default_market_id),
            market_type=self.market_type,
            instrument_id=raw.get("contract", raw.get("symbol", "")),
            event_type="QUOTE",
            bid=raw.get("bid", 0.0),
            ask=raw.get("ask", 0.0),
            bid_volume=raw.get("bid_volume", 0),
            ask_volume=raw.get("ask_volume", 0),
            metadata={"delivery_month": raw.get("delivery_month", "")},
        )

    def normalize_orderbook(self, raw: dict[str, Any]) -> UnifiedEvent:
        return self.normalize_quote(raw)

    def normalize_execution_rules(self) -> dict[str, Any]:
        return {
            "auction_based": True,
            "physical_delivery": True,
            "has_quality_grade": True,
            "settlement": "T+2",
        }


class AgriculturalAdapter(CommodityAdapter):
    """Adapter for IME agricultural contracts (graded, physical delivery)."""

    market_type = MarketType.AGRICULTURAL
    default_market_id = "ime_agricultural"


class FxFuturesAdapter(MarketAdapter):
    """Adapter for currency futures (margin, expiry, currency underlying)."""

    market_type: MarketType = MarketType.FX_FUTURES
    default_market_id = "fx_futures"

    def normalize_trade(self, raw: dict[str, Any]) -> UnifiedEvent:
        pair = raw.get("underlying_pair", raw.get("pair", ""))
        return UnifiedEvent(
            timestamp=raw.get("timestamp", now_tehran()),
            market_id=raw.get("exchange", self.default_market_id),
            market_type=self.market_type,
            instrument_id=raw.get("contract", pair),
            event_type="TRADE",
            price=raw.get("price", 0.0),
            volume=raw.get("volume", 0),
            side=raw.get("side", "buy"),
            metadata={
                "underlying_pair": pair,
                "expiry": raw.get("expiry", ""),
                "contract_size": raw.get("contract_size", 0.0),
                "open_interest": raw.get("open_interest", 0),
                "mark_price": raw.get("mark_price", 0.0),
            },
        )

    def normalize_quote(self, raw: dict[str, Any]) -> UnifiedEvent:
        pair = raw.get("underlying_pair", raw.get("pair", ""))
        return UnifiedEvent(
            timestamp=raw.get("timestamp", now_tehran()),
            market_id=raw.get("exchange", self.default_market_id),
            market_type=self.market_type,
            instrument_id=raw.get("contract", pair),
            event_type="QUOTE",
            bid=raw.get("bid", 0.0),
            ask=raw.get("ask", 0.0),
            bid_volume=raw.get("bid_volume", 0),
            ask_volume=raw.get("ask_volume", 0),
            metadata={
                "underlying_pair": pair,
                "expiry": raw.get("expiry", ""),
                "mark_price": raw.get("mark_price", 0.0),
            },
        )

    def normalize_orderbook(self, raw: dict[str, Any]) -> UnifiedEvent:
        return self.normalize_quote(raw)

    def normalize_execution_rules(self) -> dict[str, Any]:
        return {
            "margin_required": True,
            "daily_settlement": True,
            "has_expiry": True,
            "underlying": "currency",
            "settlement": "cash_or_physical",
        }


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
            MarketType.COMMODITY: CommodityAdapter(),
            MarketType.AGRICULTURAL: AgriculturalAdapter(),
            MarketType.FIXED_INCOME: FixedIncomeAdapter(),
            MarketType.SUKUK: SukukAdapter(),
            MarketType.FX_FUTURES: FxFuturesAdapter(),
        }
        adapter = adapters.get(market_type)
        if adapter is None:
            msg = f"Unsupported market type: {market_type}"
            raise ValueError(msg)
        return adapter
