"""Versioned Market Rules — historical rule sets with effective dates.

In Iran's market, rules change over time:
- Price limits changed (e.g., 5% → ±10% during COVID)
- Trading sessions changed
- Base market rules changed (yellow/orange/red tiers)
- New instruments introduced
- Settlement rules changed (T+2 → variations)

This module ensures backtests use the correct rules for each historical date.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SessionRule:
    preopen: str = "08:45"
    open: str = "09:00"
    close: str = "12:30"
    description: str = ""


@dataclass
class PriceLimitRule:
    limit_pct: float = 0.05  # 5%
    tiered: bool = False
    tiers: list[dict[str, Any]] = field(default_factory=list)
    description: str = ""


@dataclass
class AuctionRule:
    enabled: bool = True
    opening_auction: bool = True
    closing_auction: bool = True
    periodic: bool = False
    description: str = ""


@dataclass
class SettlementRule:
    t_plus: int = 2  # T+2 for stocks
    description: str = ""


@dataclass
class MarketRuleSet:
    """A complete set of market rules effective for a specific date range."""

    market_id: str = ""
    version: str = "1.0.0"
    effective_from: date = field(default_factory=date.min)
    effective_to: date | None = None  # None = still active

    session: SessionRule = field(default_factory=SessionRule)
    price_limit: PriceLimitRule = field(default_factory=PriceLimitRule)
    auction: AuctionRule = field(default_factory=AuctionRule)
    settlement: SettlementRule = field(default_factory=SettlementRule)
    queue_enabled: bool = True
    volume_base_enabled: bool = True
    short_selling_enabled: bool = False
    market_order_enabled: bool = True
    min_order_value: float = 0.0
    tick_size: float = 1.0  # Rial
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_active(self, on_date: date) -> bool:
        if on_date < self.effective_from:
            return False
        return not (self.effective_to and on_date > self.effective_to)


class MarketRuleRegistry:
    """Registry of all historical market rule sets.

    Each market has multiple rule sets with different effective dates.
    Query by (market_id, date) to get the correct rules for that time.
    """

    def __init__(self) -> None:
        self._rules: dict[str, list[MarketRuleSet]] = {}
        self._load_defaults()

    def _load_defaults(self) -> None:
        """Load default historical rule sets for Iranian markets."""
        # TSE rules — pre-COVID (before March 2020)
        self.register(
            MarketRuleSet(
                market_id="tse",
                version="pre_covid",
                effective_from=date(2018, 1, 1),
                effective_to=date(2020, 2, 19),
                session=SessionRule("08:45", "09:00", "12:30"),
                price_limit=PriceLimitRule(0.05),
                auction=AuctionRule(True, True, True),
                settlement=SettlementRule(2),
            )
        )

        # TSE rules — COVID period (±10% limit, shortened sessions)
        self.register(
            MarketRuleSet(
                market_id="tse",
                version="covid_period",
                effective_from=date(2020, 2, 20),
                effective_to=date(2020, 4, 20),
                session=SessionRule("08:45", "09:00", "12:30"),
                price_limit=PriceLimitRule(0.10),  # ±10%
                auction=AuctionRule(True, True, True),
                settlement=SettlementRule(2),
            )
        )

        # TSE rules — post-COVID standard
        self.register(
            MarketRuleSet(
                market_id="tse",
                version="post_covid_standard",
                effective_from=date(2020, 4, 21),
                effective_to=None,
                session=SessionRule("08:45", "09:00", "12:30"),
                price_limit=PriceLimitRule(0.05),
                auction=AuctionRule(True, True, True),
                settlement=SettlementRule(2),
            )
        )

        # IFB rules
        self.register(
            MarketRuleSet(
                market_id="ifb",
                version="default",
                effective_from=date(2018, 1, 1),
                effective_to=None,
                session=SessionRule("08:45", "09:00", "12:30"),
                price_limit=PriceLimitRule(0.05),
                auction=AuctionRule(True, True, True),
                settlement=SettlementRule(2),
                volume_base_enabled=True,
            )
        )

        # Base Market — tiered price limits
        self.register(
            MarketRuleSet(
                market_id="base_market",
                version="tiered_v1",
                effective_from=date(2018, 1, 1),
                effective_to=None,
                session=SessionRule("08:45", "09:00", "12:30"),
                price_limit=PriceLimitRule(
                    limit_pct=0.03,
                    tiered=True,
                    tiers=[
                        {"name": "yellow", "limit": 0.03, "description": "سهام زرد"},
                        {"name": "orange", "limit": 0.02, "description": "سهام نارنجی"},
                        {"name": "red", "limit": 0.01, "description": "سهام قرمز"},
                    ],
                ),
                auction=AuctionRule(True, False, False, periodic=True),
                settlement=SettlementRule(2),
                queue_enabled=True,
                volume_base_enabled=False,
            )
        )

        # ETF
        self.register(
            MarketRuleSet(
                market_id="etf",
                version="default",
                effective_from=date(2018, 1, 1),
                effective_to=None,
                session=SessionRule("08:45", "09:00", "12:30"),
                price_limit=PriceLimitRule(0.05),
                auction=AuctionRule(True, True, True),
                settlement=SettlementRule(2),
                volume_base_enabled=False,
            )
        )

        # Bonds
        self.register(
            MarketRuleSet(
                market_id="bonds",
                version="default",
                effective_from=date(2018, 1, 1),
                effective_to=None,
                session=SessionRule("08:45", "09:00", "12:30"),
                price_limit=PriceLimitRule(0.01),
                auction=AuctionRule(False, False, False),
                settlement=SettlementRule(2),
            )
        )

        # IME (Commodity Exchange)
        self.register(
            MarketRuleSet(
                market_id="ime",
                version="default",
                effective_from=date(2018, 1, 1),
                effective_to=None,
                session=SessionRule("11:45", "12:00", "18:00"),
                price_limit=PriceLimitRule(0.05),
                auction=AuctionRule(True, True, True),
                settlement=SettlementRule(2),
            )
        )

    def register(self, rule_set: MarketRuleSet) -> None:
        if rule_set.market_id not in self._rules:
            self._rules[rule_set.market_id] = []
        self._rules[rule_set.market_id].append(rule_set)
        self._rules[rule_set.market_id].sort(key=lambda r: r.effective_from)

    def get_rules(self, market_id: str, on_date: date) -> MarketRuleSet | None:
        """Get the active rule set for a market on a specific date."""
        rules = self._rules.get(market_id, [])
        # Search from most recent to oldest
        for rule_set in reversed(rules):
            if rule_set.is_active(on_date):
                return rule_set
        # Fallback to most recent
        return rules[-1] if rules else None

    def get_all_versions(self, market_id: str) -> list[MarketRuleSet]:
        return self._rules.get(market_id, [])

    def export_rules(self, market_id: str, on_date: date) -> dict[str, Any]:
        """Export rules as a serializable dict for run manifests."""
        rule = self.get_rules(market_id, on_date)
        if not rule:
            return {}
        return {
            "market_id": rule.market_id,
            "version": rule.version,
            "effective_from": rule.effective_from.isoformat(),
            "effective_to": rule.effective_to.isoformat() if rule.effective_to else None,
            "price_limit_pct": rule.price_limit.limit_pct,
            "session": {"open": rule.session.open, "close": rule.session.close},
            "settlement_t": rule.settlement.t_plus,
        }
