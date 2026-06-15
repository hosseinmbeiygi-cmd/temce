from __future__ import annotations

from dataclasses import dataclass


@dataclass
class IranCommissionModel:
    broker_buy_pct: float = 0.004
    broker_sell_pct: float = 0.004
    tax_pct: float = 0.005
    clearing_fee_pct: float = 0.00085
    settlement_fee: float = 0.0
    min_commission: float = 0.0
    max_commission: float = float("inf")
    tiered: bool = False

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
        tax = principal * self.tax_pct
        return {
            "broker": broker,
            "tax": tax,
            "clearing": principal * self.clearing_fee_pct,
            "total": broker + tax + principal * self.clearing_fee_pct,
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
