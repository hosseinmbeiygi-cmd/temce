"""Futures Risk — Margin & Liquidation calculator for IME coin futures.

Implements the contract spec from the Antigravity Gold prompt:

  • contract_size: 10 coin Bahar Azadi
  • initial_margin: 10%  (1 / leverage)
  • maintenance_margin: 5%
  • leverage: 10 (default)

Formulas:

  liquidation_price_long  = entry * (1 - (initial_margin - maintenance_margin))
  liquidation_price_short = entry * (1 + (initial_margin - maintenance_margin))

  health_ratio = equity / used_margin
    > 2.0  → SAFE     (green)
    1.2-2 → WARNING  (yellow)
    < 1.2  → CRITICAL (red)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PositionType = Literal["LONG", "SHORT"]
AlertLevel = Literal["SAFE", "WARNING", "CRITICAL"]


class FuturesRiskCalculator:
    """محاسبه‌گر ریسک و مارجین برای معاملات آتی سکه (IME)."""

    # IME coin futures spec
    CONTRACT_SIZE = 10  # 10 سکه بهار آزادی
    MAINTENANCE_MARGIN_RATIO = 0.05

    def __init__(self, leverage: int = 10) -> None:
        if leverage < 1 or leverage > 20:
            raise ValueError("leverage must be in [1, 20]")
        self.leverage = leverage
        self.initial_margin_ratio = 1.0 / leverage
        self.maintenance_margin_ratio = self.MAINTENANCE_MARGIN_RATIO
        self.margin_buffer = self.initial_margin_ratio - self.maintenance_margin_ratio

    # ── Pure margin math ──────────────────────────────────────────

    def contract_value(self, entry_price: float, quantity: int) -> float:
        return entry_price * quantity * self.CONTRACT_SIZE

    def initial_margin(self, entry_price: float, quantity: int) -> float:
        return self.contract_value(entry_price, quantity) * self.initial_margin_ratio

    def maintenance_margin(self, entry_price: float, quantity: int) -> float:
        return self.contract_value(entry_price, quantity) * self.maintenance_margin_ratio

    def liquidation_price(self, entry_price: float, position_type: PositionType) -> float:
        if position_type == "LONG":
            return entry_price * (1 - self.margin_buffer)
        return entry_price * (1 + self.margin_buffer)

    # ── Health & alerts ──────────────────────────────────────────

    @staticmethod
    def health_ratio(equity: float, used_margin: float) -> float:
        if used_margin <= 0:
            return float("inf")
        return equity / used_margin

    def distance_to_liquidation_pct(
        self, current_price: float, entry_price: float, position_type: PositionType
    ) -> float:
        liq = self.liquidation_price(entry_price, position_type)
        if position_type == "LONG":
            return ((current_price - liq) / current_price) * 100.0
        return ((liq - current_price) / current_price) * 100.0

    def margin_call_alert(
        self,
        current_price: float,
        entry_price: float,
        position_type: PositionType,
        equity: float,
        position_value: float,
    ) -> dict:
        """هشدار کال‌مارجین + سایر معیارها."""
        used_margin = position_value * self.initial_margin_ratio
        health = self.health_ratio(equity, used_margin)
        distance = self.distance_to_liquidation_pct(current_price, entry_price, position_type)
        liq = self.liquidation_price(entry_price, position_type)

        if health < 1.2:
            level: AlertLevel = "CRITICAL"
            msg = f"⚠️ کال‌مارجین نزدیک است! فاصله تا لیکوئید: {distance:.2f}%"
        elif health < 2.0:
            level = "WARNING"
            msg = f"⚡ هشدار مارجین. نسبت سلامت: {health:.2f}"
        else:
            level = "SAFE"
            msg = f"✅ پوزیشن سالم. نسبت سلامت: {health:.2f}"

        return {
            "alert_level": level,
            "alert_message": msg,
            "liquidation_price": round(liq, 2),
            "distance_to_liquidation_pct": round(distance, 2),
            "health_ratio": round(health, 2),
        }

    # ── All-in-one calculator (the API endpoint uses this) ──────

    @dataclass
    class FullResult:
        contract_value: float
        initial_margin: float
        maintenance_margin: float
        liquidation_price: float
        health_ratio: float | None
        distance_to_liquidation_pct: float | None
        alert_level: AlertLevel | None
        alert_message: str | None
        recommended_stop_loss: float | None
        unrealized_pnl_irr: float | None
        unrealized_pnl_pct: float | None

    def calculate(
        self,
        entry_price: float,
        position_type: PositionType,
        quantity: int,
        current_price: float | None = None,
        account_equity: float | None = None,
    ) -> FullResult:
        """محاسبه کامل: مارجین + لیکوئید + (اختیاری) Health + Stop Loss پیشنهادی."""
        contract_value = self.contract_value(entry_price, quantity)
        init_margin = self.initial_margin(entry_price, quantity)
        maint_margin = self.maintenance_margin(entry_price, quantity)
        liq = self.liquidation_price(entry_price, position_type)

        # Stop loss پیشنهادی: 1.5× maintenance margin buffer
        # ساده‌ترین حالت: SL با فاصله 2× margin_buffer از ورود
        sl_buffer = self.margin_buffer * 2
        if position_type == "LONG":
            recommended_sl = entry_price * (1 - sl_buffer)
        else:
            recommended_sl = entry_price * (1 + sl_buffer)

        # اختیاری: محاسبات real-time
        health = distance = alert_level = alert_msg = None
        unrealized_pnl_irr = unrealized_pnl_pct = None
        if current_price is not None and account_equity is not None and account_equity > 0:
            alert = self.margin_call_alert(current_price, entry_price, position_type, account_equity, contract_value)
            health = alert["health_ratio"]
            distance = alert["distance_to_liquidation_pct"]
            alert_level = alert["alert_level"]
            alert_msg = alert["alert_message"]

            # P&L (بدون احتساب کارمزد)
            direction = 1 if position_type == "LONG" else -1
            unrealized_pnl_irr = (current_price - entry_price) * direction * quantity * self.CONTRACT_SIZE
            unrealized_pnl_pct = ((current_price - entry_price) / entry_price) * 100.0 * direction

        return self.FullResult(
            contract_value=round(contract_value, 2),
            initial_margin=round(init_margin, 2),
            maintenance_margin=round(maint_margin, 2),
            liquidation_price=round(liq, 2),
            health_ratio=health,
            distance_to_liquidation_pct=distance,
            alert_level=alert_level,
            alert_message=alert_msg,
            recommended_stop_loss=round(recommended_sl, 2),
            unrealized_pnl_irr=(round(unrealized_pnl_irr, 2) if unrealized_pnl_irr is not None else None),
            unrealized_pnl_pct=(round(unrealized_pnl_pct, 2) if unrealized_pnl_pct is not None else None),
        )
