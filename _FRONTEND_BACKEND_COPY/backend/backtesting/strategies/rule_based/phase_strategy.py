"""Phase-based Smart Money strategy for backtesting.

Trades based on Smart Money Phase Engine classification.
Entry: When phase transitions to a bullish phase.
Exit: When phase transitions to neutral or bearish phase.
"""

from __future__ import annotations

from typing import Any

from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent
from services.smart_money.config_loader import (
    SmartMoneyConfig,
    classify_phase_from_config,
    load_config,
)

# Phase priority for trading decisions (lower = more bullish)
PHASE_PRIORITY: dict[str, int] = {
    "confirmed_smart_money": 1,
    "breakout_ready": 2,
    "float_lock": 3,
    "active_absorption": 4,
    "early_accumulation": 5,
    "neutral": 6,
}

# Phases that trigger entry
BULLISH_PHASES = {"confirmed_smart_money", "breakout_ready", "float_lock", "active_absorption"}


class PhaseStrategy(BaseStrategy):
    """Smart Money Phase-based trading strategy.

    Parameters:
        config_path: Path to smart_money.yaml config file
        min_phase_priority: Minimum phase priority to enter (default: 3 = float_lock)
        exit_phase_priority: Phase priority threshold to exit (default: 5 = early_accumulation)
        lookback_days: Days of history for feature computation
    """

    def __init__(
        self,
        instrument_id: str = "",
        config_path: str | None = None,
        min_phase_priority: int = 3,
        exit_phase_priority: int = 5,
        lookback_days: int = 20,
        sizing_method: str = "fixed",
        sizing_value: float = 1000.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            name="PhaseStrategy",
            sizing_method=sizing_method,
            sizing_value=sizing_value,
        )
        self.instrument_id = instrument_id
        self._config: SmartMoneyConfig | None = None
        self._config_path = config_path
        self._min_phase_priority = min_phase_priority
        self._exit_phase_priority = exit_phase_priority
        self._lookback_days = lookback_days

        # State
        self._history: list[dict[str, Any]] = []
        self._current_phase: str = "neutral"
        self._phase_history: list[str] = []
        self._entry_price: float | None = None

    def _ensure_config(self) -> SmartMoneyConfig:
        if self._config is None:
            self._config = load_config(self._config_path)
        return self._config

    def _compute_phase(self, bars: list[dict[str, Any]]) -> str:
        """Compute phase from recent bars using Smart Money Engine."""
        if len(bars) < self._lookback_days:
            return "neutral"

        cfg = self._ensure_config()
        recent = bars[-self._lookback_days :]

        # Extract features from bars (simplified - in production use actual layers)
        # This is a placeholder that uses basic price/volume features
        closes = [b.get("close", 0) for b in recent]
        volumes = [b.get("volume", 0) for b in recent]

        if not closes or closes[-1] == 0:
            return "neutral"

        # Compute basic features
        avg_vol = sum(volumes) / len(volumes) if volumes else 1
        price_change = (closes[-1] - closes[0]) / closes[0] if closes[0] else 0
        vol_ratio = volumes[-1] / avg_vol if avg_vol > 0 else 1

        # Simple phase scoring (placeholder - real implementation uses all 9 layers)
        scores = {
            "smc": min(1.0, max(0.0, 0.5 + price_change * 2 + (vol_ratio - 1) * 0.3)),
            "acc": min(1.0, max(0.0, 0.5 + price_change * 1.5)),
            "abs_final": min(1.0, max(0.0, 0.5 + vol_ratio * 0.2)),
            "fl": min(1.0, max(0.0, 0.5 - abs(price_change) * 0.5)),
            "br": min(1.0, max(0.0, 0.5 + price_change * 1.2 + vol_ratio * 0.2)),
            "ess": min(1.0, max(0.0, 0.5 - abs(price_change) * 0.3)),
            "rrs": min(1.0, max(0.0, 0.5 + price_change * 1.0)),
            "rmr_n": min(1.0, max(0.0, 0.5 + price_change * 0.8)),
            "dps_n": min(1.0, max(0.0, 0.5 + vol_ratio * 0.3)),
            "rp_n": min(1.0, max(0.0, 0.5 + price_change * 1.5)),
        }

        return classify_phase_from_config(cfg, scores)

    def on_bar(self, bar: dict[str, Any]) -> list[OrderEvent]:
        """Process each bar and generate orders based on phase."""
        orders: list[OrderEvent] = []
        self._history.append(bar)

        # Keep history bounded
        if len(self._history) > self._lookback_days * 3:
            self._history = self._history[-self._lookback_days * 2 :]

        # Compute current phase
        raw_phase = self._compute_phase(self._history)
        self._phase_history.append(raw_phase)

        # Apply hysteresis (simplified)
        prev_phase = self._current_phase
        if raw_phase != prev_phase:
            # Check if phase changed
            self._current_phase = raw_phase

        # Trading logic
        price = bar.get("close", 0)
        if price <= 0:
            return orders

        phase_prio = PHASE_PRIORITY.get(self._current_phase, 6)
        prev_prio = PHASE_PRIORITY.get(prev_phase, 6)

        # Entry: phase improved to bullish level
        if phase_prio <= self._min_phase_priority and prev_prio > self._min_phase_priority:
            if not self._entry_price:
                qty = self._compute_quantity(price)
                if qty > 0 and self.ctx and self.ctx.cash >= qty * price:
                    self._entry_price = price
                    orders.append(
                        OrderEvent(
                            instrument_id=self.instrument_id,
                            side="buy",
                            quantity=qty,
                            price=price,
                            reason=f"Phase entry: {self._current_phase}",
                        )
                    )

        # Exit: phase degraded
        elif self._entry_price and phase_prio >= self._exit_phase_priority:
            if self.ctx:
                position = self.ctx.positions.get(self.instrument_id)
                if position and position.quantity > 0:
                    orders.append(
                        OrderEvent(
                            instrument_id=self.instrument_id,
                            side="sell",
                            quantity=position.quantity,
                            price=price,
                            reason=f"Phase exit: {self._current_phase}",
                        )
                    )
                    self._entry_price = None

        # Stop loss: -5%
        if self._entry_price and price < self._entry_price * 0.95:
            if self.ctx:
                position = self.ctx.positions.get(self.instrument_id)
                if position and position.quantity > 0:
                    orders.append(
                        OrderEvent(
                            instrument_id=self.instrument_id,
                            side="sell",
                            quantity=position.quantity,
                            price=price,
                            reason="Stop loss",
                        )
                    )
                    self._entry_price = None

        return orders

    def reset(self) -> None:
        super().reset()
        self._history.clear()
        self._current_phase = "neutral"
        self._phase_history.clear()
        self._entry_price = None
