from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


# Market Constants
DEFAULT_MAX_CHANGE_PCT = 5.0
BASE_MARKET_MAX_CHANGE_PCT = 3.0
DEFAULT_TICK_SIZE = 0.1
BONDS_TICK_SIZE = 0.01
DEFAULT_AUCTION_DURATION = 30
BASE_MARKET_AUCTION_DURATION = 30
TSE_OPEN_TIME = "09:00"
TSE_CLOSE_TIME = "12:30"
TSE_PRE_OPEN_TIME = "08:45"
IME_OPEN_TIME = "12:00"
IME_CLOSE_TIME = "18:00"
IME_PRE_OPEN_TIME = "11:45"

@dataclass
class SessionRules:
    pre_open: str = ""
    open: str = ""
    close: str = ""
    pre_open_duration_minutes: int = 30



@dataclass
class PriceLimitRules:
    max_change_pct: float = 5.0
    dynamic_bands: bool = False
    yellow_pct: float = 0.0
    orange_pct: float = 0.0
    red_pct: float = 0.0


@dataclass
class TickSizeRules:
    base_tick: float = 0.1
    tiered: bool = False
    tiers: list[dict[str, float]] = field(default_factory=list)


@dataclass
class AuctionRules:
    enabled: bool = True
    auction_type: str = "open"  # open, close, periodic
    duration_minutes: int = 30


@dataclass
class OrderValidationRules:
    min_quantity: int = 1
    max_quantity: int = 1_000_000_000
    min_value: float = 0.0
    max_value: float = 0.0
    allow_market_order: bool = True
    allow_limit_order: bool = True


class MarketPolicy(ABC):
    market_id: str = ""
    name: str = ""

    @abstractmethod
    def get_session_rules(self) -> SessionRules: ...

    @abstractmethod
    def get_price_limit_rules(self) -> PriceLimitRules: ...

    @abstractmethod
    def get_tick_size_rules(self) -> TickSizeRules: ...

    @abstractmethod
    def get_auction_rules(self) -> AuctionRules: ...

    @abstractmethod
    def get_order_validation_rules(self) -> OrderValidationRules: ...

    def get_metadata(self) -> dict[str, Any]:
        return {}


class TSEMarketPolicy(MarketPolicy):
    market_id = "tse"
    name = "Tehran Stock Exchange"

    def get_session_rules(self) -> SessionRules:
        return SessionRules(pre_open=TSE_PRE_OPEN_TIME, open=TSE_OPEN_TIME, close=TSE_CLOSE_TIME)

    def get_price_limit_rules(self) -> PriceLimitRules:
        return PriceLimitRules(max_change_pct=DEFAULT_MAX_CHANGE_PCT)

    def get_tick_size_rules(self) -> TickSizeRules:
        return TickSizeRules(base_tick=DEFAULT_TICK_SIZE)

    def get_auction_rules(self) -> AuctionRules:
        return AuctionRules(enabled=True, auction_type="open", duration_minutes=DEFAULT_AUCTION_DURATION)

    def get_order_validation_rules(self) -> OrderValidationRules:
        return OrderValidationRules(allow_market_order=True, allow_limit_order=True)


class IFBMarketPolicy(MarketPolicy):
    market_id = "ifb"
    name = "Iran Fara Bourse"

    def get_session_rules(self) -> SessionRules:
        return SessionRules(pre_open=TSE_PRE_OPEN_TIME, open=TSE_OPEN_TIME, close=TSE_CLOSE_TIME)

    def get_price_limit_rules(self) -> PriceLimitRules:
        return PriceLimitRules(max_change_pct=DEFAULT_MAX_CHANGE_PCT)

    def get_tick_size_rules(self) -> TickSizeRules:
        return TickSizeRules(base_tick=DEFAULT_TICK_SIZE)

    def get_auction_rules(self) -> AuctionRules:
        return AuctionRules(enabled=True, auction_type="open", duration_minutes=DEFAULT_AUCTION_DURATION)

    def get_order_validation_rules(self) -> OrderValidationRules:
        return OrderValidationRules(allow_market_order=True, allow_limit_order=True)


class BaseMarketPolicy(MarketPolicy):
    market_id = "base_market"
    name = "Base Market"

    def get_session_rules(self) -> SessionRules:
        return SessionRules(pre_open="08:45", open="09:00", close="12:30")

    def get_price_limit_rules(self) -> PriceLimitRules:
        return PriceLimitRules(
            max_change_pct=3.0,
            dynamic_bands=True,
            yellow_pct=3.0,
            orange_pct=2.0,
            red_pct=1.0,
        )

    def get_tick_size_rules(self) -> TickSizeRules:
        return TickSizeRules(base_tick=0.1)

    def get_auction_rules(self) -> AuctionRules:
        return AuctionRules(enabled=True, auction_type="periodic", duration_minutes=30)

    def get_order_validation_rules(self) -> OrderValidationRules:
        return OrderValidationRules(allow_market_order=False, allow_limit_order=True)


class ETFMarketPolicy(MarketPolicy):
    market_id = "etf"
    name = "ETF Market"

    def get_session_rules(self) -> SessionRules:
        return SessionRules(pre_open=TSE_PRE_OPEN_TIME, open=TSE_OPEN_TIME, close=TSE_CLOSE_TIME)

    def get_price_limit_rules(self) -> PriceLimitRules:
        return PriceLimitRules(max_change_pct=DEFAULT_MAX_CHANGE_PCT)

    def get_tick_size_rules(self) -> TickSizeRules:
        return TickSizeRules(base_tick=DEFAULT_TICK_SIZE)

    def get_auction_rules(self) -> AuctionRules:
        return AuctionRules(enabled=True, auction_type="open", duration_minutes=DEFAULT_AUCTION_DURATION)

    def get_order_validation_rules(self) -> OrderValidationRules:
        return OrderValidationRules(allow_market_order=True, allow_limit_order=True)

    def get_metadata(self) -> dict[str, Any]:
        return {"nav_reference": True, "market_maker": "optional"}


class BondsMarketPolicy(MarketPolicy):
    market_id = "bonds"
    name = "Bonds Market"

    def get_session_rules(self) -> SessionRules:
        return SessionRules(pre_open="08:45", open="09:00", close="12:30")

    def get_price_limit_rules(self) -> PriceLimitRules:
        return PriceLimitRules(max_change_pct=1.0)

    def get_tick_size_rules(self) -> TickSizeRules:
        return TickSizeRules(base_tick=0.01)

    def get_auction_rules(self) -> AuctionRules:
        return AuctionRules(enabled=False)

    def get_order_validation_rules(self) -> OrderValidationRules:
        return OrderValidationRules(allow_market_order=True, allow_limit_order=True)

    def get_metadata(self) -> dict[str, Any]:
        return {"yield_calculation": True, "accrued_interest": True}


class DerivativesMarketPolicy(MarketPolicy):
    market_id = "derivatives"
    name = "Derivatives Market"

    def get_session_rules(self) -> SessionRules:
        return SessionRules(pre_open="08:45", open="09:00", close="12:30")

    def get_price_limit_rules(self) -> PriceLimitRules:
        return PriceLimitRules(max_change_pct=0.0, dynamic_bands=True)

    def get_tick_size_rules(self) -> TickSizeRules:
        return TickSizeRules(base_tick=0.1)

    def get_auction_rules(self) -> AuctionRules:
        return AuctionRules(enabled=False)

    def get_order_validation_rules(self) -> OrderValidationRules:
        return OrderValidationRules(allow_market_order=True, allow_limit_order=True)

    def get_metadata(self) -> dict[str, Any]:
        return {"margin_required": True, "daily_settlement": True, "expiry": "contract_specific"}


class IMEMarketPolicy(MarketPolicy):
    market_id = "ime"
    name = "Iran Mercantile Exchange"

    def get_session_rules(self) -> SessionRules:
        return SessionRules(pre_open=TSE_PRE_OPEN_TIME, open=TSE_OPEN_TIME, close=TSE_CLOSE_TIME)

    def get_price_limit_rules(self) -> PriceLimitRules:
        return PriceLimitRules(max_change_pct=DEFAULT_MAX_CHANGE_PCT)

    def get_tick_size_rules(self) -> TickSizeRules:
        return TickSizeRules(base_tick=DEFAULT_TICK_SIZE)

    def get_auction_rules(self) -> AuctionRules:
        return AuctionRules(enabled=True, auction_type="open", duration_minutes=DEFAULT_AUCTION_DURATION)

    def get_order_validation_rules(self) -> OrderValidationRules:
        return OrderValidationRules(allow_market_order=True, allow_limit_order=True)

    def get_metadata(self) -> dict[str, Any]:
        return {"contract_spec": "required"}


class EnergyMarketPolicy(MarketPolicy):
    market_id = "energy"
    name = "Energy Exchange"

    def get_session_rules(self) -> SessionRules:
        return SessionRules(pre_open="11:45", open="12:00", close="18:00")

    def get_price_limit_rules(self) -> PriceLimitRules:
        return PriceLimitRules(max_change_pct=5.0)

    def get_tick_size_rules(self) -> TickSizeRules:
        return TickSizeRules(base_tick=0.1)

    def get_auction_rules(self) -> AuctionRules:
        return AuctionRules(enabled=True, auction_type="periodic", duration_minutes=60)

    def get_order_validation_rules(self) -> OrderValidationRules:
        return OrderValidationRules(allow_market_order=False, allow_limit_order=True)

    def get_metadata(self) -> dict[str, Any]:
        return {"block_trades": True, "delivery_rules": True}


class MarketPolicyRegistry:
    def __init__(self) -> None:
        self._policies: dict[str, MarketPolicy] = {}

    def register(self, policy: MarketPolicy) -> None:
        self._policies[policy.market_id] = policy

    def get(self, market_id: str) -> MarketPolicy:
        if market_id not in self._policies:
            msg = f"Unknown market: {market_id}"
            raise KeyError(msg)
        return self._policies[market_id]

    def has(self, market_id: str) -> bool:
        return market_id in self._policies

    def all_markets(self) -> list[str]:
        return list(self._policies.keys())

    @classmethod
    def create_default(cls) -> MarketPolicyRegistry:
        registry = cls()
        registry.register(TSEMarketPolicy())
        registry.register(IFBMarketPolicy())
        registry.register(BaseMarketPolicy())
        registry.register(ETFMarketPolicy())
        registry.register(BondsMarketPolicy())
        registry.register(DerivativesMarketPolicy())
        registry.register(IMEMarketPolicy())
        registry.register(EnergyMarketPolicy())
        return registry
