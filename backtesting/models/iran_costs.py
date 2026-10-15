from __future__ import annotations

from dataclasses import dataclass

from backtesting.costs.iran_costs import (
    BROKER_PCT,
    CLEARING_FEE_PCT,
    DEFAULT_MARKET,
    SELL_TAX_PCT,
)


@dataclass
class IranCommissionModel:
    # Rates are single-sourced from backtesting.costs.iran_costs (audit F1).
    # Totals follow the 1405 all-in market table (tax inside sell rate);
    # broker/clearing legs are informational, tax is the residual so that
    # broker + tax + clearing == canonical total EXACTLY.
    broker_buy_pct: float = BROKER_PCT
    broker_sell_pct: float = BROKER_PCT
    tax_pct: float = SELL_TAX_PCT
    clearing_fee_pct: float = CLEARING_FEE_PCT
    settlement_fee: float = 0.0
    min_commission: float = 0.0
    max_commission: float = float("inf")
    tiered: bool = False
    market: str = DEFAULT_MARKET

    def _canonical_total(self, side: str, price: float, quantity: int) -> float:
        from backtesting.costs.iran_costs import IranTransactionCosts

        return IranTransactionCosts(market=self.market).compute(side, price, quantity)

    def compute_buy(self, price: float, quantity: int) -> dict[str, float]:
        principal = price * quantity
        broker = max(principal * self.broker_buy_pct, self.min_commission)
        if self.max_commission and broker > self.max_commission:
            broker = self.max_commission
        return {
            "broker": broker,
            "tax": 0.0,
            "clearing": principal * self.clearing_fee_pct,
            "total": broker + principal * self.clearing_fee_pct,
        }

    def compute_sell(self, price: float, quantity: int) -> dict[str, float]:
        principal = price * quantity
        broker = max(principal * self.broker_sell_pct, self.min_commission)
        if self.max_commission and broker > self.max_commission:
            broker = self.max_commission
        clearing = principal * self.clearing_fee_pct
        total = self._canonical_total("sell", price, quantity)
        tax = max(total - broker - clearing, 0.0)
        return {
            "broker": broker,
            "tax": tax,
            "clearing": clearing,
            "total": total,
        }

    def compute_total(self, buy_price: float, buy_qty: int, sell_price: float, sell_qty: int) -> dict[str, float]:
        buy_costs = self.compute_buy(buy_price, buy_qty)
        sell_costs = self.compute_sell(sell_price, sell_qty)
        return {
            "buy_costs": buy_costs,
            "sell_costs": sell_costs,
            "total_commission": buy_costs["total"] + sell_costs["total"],
        }


@dataclass
class SettlementModel:
    settlement_days: int = 2
    settlement_currency: str = "IRR"

    def days_to_settlement(self, trade_date: str, side: str = "buy") -> int:
        return self.settlement_days

    def settlement_value(self, price: float, quantity: int, costs: dict[str, float]) -> float:
        return price * quantity + costs.get("total", 0.0)
