"""Canonical Iranian-market transaction cost model.

Single source of truth (audit finding F1). Rates come from the 1405
all-in schedule in ``domain.trading.iran_costs.MARKET_RATES`` — the 0.5%
transfer tax is already INSIDE the equity sell rates, never added on top.

Every fill producer charges through ``IranTransactionCosts.compute(...)``
so all backtest paths converge on identical costs (audit finding F2).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Rates single-sourced from the canonical module (P1-3) — no local copies.
from domain.trading.iran_costs import (
    BROKER_PCT,
    CLEARING_FEE_PCT,
    DEFAULT_MARKET,
    SELL_TAX_PCT,
    buy_rate,
    sell_rate,
)


def normalize_side(side: Any) -> str:
    """Return a lowercase 'buy'/'sell' string for enum or plain-string sides."""
    if hasattr(side, "value"):  # StrEnum / Enum
        return str(side.value).lower()
    return str(side).lower()


@dataclass(frozen=True)
class IranTransactionCosts:
    """Canonical Iranian transaction cost model.

    ``compute(side, price, quantity)`` returns the total cost of a single
    fill using the market's all-in 1405 rate. Component fields below are
    kept for decomposition/display only.
    """

    broker_pct: float = BROKER_PCT
    sell_tax_pct: float = SELL_TAX_PCT
    clearing_fee_pct: float = CLEARING_FEE_PCT
    min_commission: float = 0.0
    market: str = DEFAULT_MARKET

    def buy_cost(self, price: float, quantity: int) -> float:
        principal = max(float(price), 0.0) * max(int(quantity), 0)
        return max(principal * buy_rate(self.market), self.min_commission)

    def sell_cost(self, price: float, quantity: int) -> float:
        principal = max(float(price), 0.0) * max(int(quantity), 0)
        return max(principal * sell_rate(self.market), self.min_commission)

    def compute(self, side: Any, price: float, quantity: int) -> float:
        """Total transaction cost for a single fill (tax inside sell rate)."""
        if normalize_side(side) == "sell":
            return self.sell_cost(price, quantity)
        return self.buy_cost(price, quantity)

    def round_trip_cost(
        self,
        buy_price: float,
        buy_qty: int,
        sell_price: float,
        sell_qty: int,
    ) -> float:
        return self.buy_cost(buy_price, buy_qty) + self.sell_cost(sell_price, sell_qty)

    @classmethod
    def from_config(cls, path: str = "config/backtest_costs.yaml") -> IranTransactionCosts:
        """Build from YAML config (no hardcoded rates in engine code)."""
        try:
            import yaml  # type: ignore

            with open(path, encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
        except Exception:
            cfg = {}
        market = str(cfg.get("market", DEFAULT_MARKET))
        # Explicit per-side overrides win over the market table when present.
        buy = cfg.get("buy_pct")
        sell = cfg.get("sell_pct")
        obj = cls(
            broker_pct=float(cfg.get("broker_pct", BROKER_PCT)),
            sell_tax_pct=float(cfg.get("sell_tax_pct", SELL_TAX_PCT)),
            clearing_fee_pct=float(cfg.get("clearing_fee_pct", CLEARING_FEE_PCT)),
            min_commission=float(cfg.get("min_commission", 0.0)),
            market=market,
        )
        if buy is not None or sell is not None:
            import domain.trading.iran_costs as _m

            b = float(buy) if buy is not None else _m.buy_rate(market)
            s = float(sell) if sell is not None else _m.sell_rate(market)
            t = _m.sell_tax(market)  # explicit tax param preserved, never re-added
            _m.MARKET_RATES[f"config:{market}"] = (b, s, t)
            obj = cls(
                broker_pct=obj.broker_pct,
                sell_tax_pct=obj.sell_tax_pct,
                clearing_fee_pct=obj.clearing_fee_pct,
                min_commission=obj.min_commission,
                market=f"config:{market}",
            )
        return obj


# Default canonical instance (frozen → safe to share across engines)
DEFAULT_IRAN_COSTS = IranTransactionCosts()
