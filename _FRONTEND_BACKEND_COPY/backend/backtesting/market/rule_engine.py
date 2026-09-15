from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from backtesting.market.policies import (
    AuctionRules,
    MarketPolicy,
    MarketPolicyRegistry,
    OrderValidationRules,
    PriceLimitRules,
    SessionRules,
    TickSizeRules,
)
from backtesting.types import OrderEvent
from domain.markets.enums import MarketStatus


@dataclass
class MarketRuleSet:
    session: SessionRules = field(default_factory=SessionRules)
    price_limit: PriceLimitRules = field(default_factory=PriceLimitRules)
    tick_size: TickSizeRules = field(default_factory=TickSizeRules)
    auction: AuctionRules = field(default_factory=AuctionRules)
    order_validation: OrderValidationRules = field(default_factory=OrderValidationRules)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_policy(cls, policy: MarketPolicy) -> MarketRuleSet:
        return cls(
            session=policy.get_session_rules(),
            price_limit=policy.get_price_limit_rules(),
            tick_size=policy.get_tick_size_rules(),
            auction=policy.get_auction_rules(),
            order_validation=policy.get_order_validation_rules(),
            metadata=policy.get_metadata(),
        )


class MarketRuleEngine:
    def __init__(self, registry: MarketPolicyRegistry | None = None) -> None:
        self._registry = registry or MarketPolicyRegistry.create_default()
        self._cache: dict[str, MarketRuleSet] = {}

    def get_rules(self, market_id: str) -> MarketRuleSet:
        if market_id not in self._cache:
            policy = self._registry.get(market_id)
            self._cache[market_id] = MarketRuleSet.from_policy(policy)
        return self._cache[market_id]

    def validate_order(self, market_id: str, order: OrderEvent) -> tuple[bool, str]:
        rules = self.get_rules(market_id)
        validation = rules.order_validation

        if order.quantity < validation.min_quantity:
            return False, f"Quantity {order.quantity} below minimum {validation.min_quantity}"

        if validation.max_quantity > 0 and order.quantity > validation.max_quantity:
            return False, f"Quantity {order.quantity} above maximum {validation.max_quantity}"

        if validation.min_value > 0 and (order.price * order.quantity) < validation.min_value:
            return False, f"Order value below minimum {validation.min_value}"

        if validation.max_value > 0 and (order.price * order.quantity) > validation.max_value:
            return False, f"Order value above maximum {validation.max_value}"

        return True, ""

    def apply_price_limit(self, market_id: str, reference_price: float, current_price: float) -> float:
        rules = self.get_rules(market_id)
        if rules.price_limit.dynamic_bands:
            return self._apply_dynamic_limit(rules.price_limit, reference_price, current_price)
        max_change = reference_price * (rules.price_limit.max_change_pct / 100.0)
        lower = reference_price - max_change
        upper = reference_price + max_change
        return max(lower, min(current_price, upper))

    def _apply_dynamic_limit(self, rules: PriceLimitRules, reference: float, price: float) -> float:
        if reference == 0:
            return price
        change_pct = abs((price - reference) / reference) * 100
        if change_pct <= rules.yellow_pct:
            band = rules.yellow_pct
        elif change_pct <= rules.orange_pct:
            band = rules.orange_pct
        else:
            band = rules.red_pct
        limit = reference * (band / 100.0)
        lower = reference - limit
        upper = reference + limit
        return max(lower, min(price, upper))

    def check_session_status(
        self,
        market_id: str,
        current_time: datetime,
    ) -> MarketStatus:
        rules = self.get_rules(market_id)
        time_str = current_time.strftime("%H:%M")

        if rules.session.pre_open and rules.session.pre_open <= time_str < rules.session.open:
            return MarketStatus.PRE_OPEN
        if rules.session.open and rules.session.close:
            if rules.session.open <= time_str <= rules.session.close:
                return MarketStatus.OPEN
        return MarketStatus.CLOSED

    def validate_price_tick(self, market_id: str, price: float) -> float:
        rules = self.get_rules(market_id)
        tick = rules.tick_size.base_tick
        if tick <= 0:
            return price
        return round(price / tick) * tick

    def is_auction_time(self, market_id: str, current_time: datetime) -> bool:
        rules = self.get_rules(market_id)
        if not rules.auction.enabled:
            return False
        from datetime import timedelta

        open_dt = datetime.strptime(rules.session.open, "%H:%M").replace(
            year=current_time.year, month=current_time.month, day=current_time.day
        )
        auction_start = open_dt - timedelta(minutes=rules.auction.duration_minutes)
        return auction_start <= current_time < open_dt

    def register_policy(self, market_id: str, policy: MarketPolicy) -> None:
        self._registry.register(policy)
        self._cache.pop(market_id, None)
