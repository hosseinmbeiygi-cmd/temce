"""ML Signal Strategy — generates BUY/SELL signals based on predicted price changes.

This strategy takes pre-computed ML predictions (predicted_change_pct) for each
bar and trades based on configurable thresholds:
- Buy when predicted_change_pct > buy_threshold
- Sell when predicted_change_pct < sell_threshold
- Hold otherwise

Two modes:
1. Pre-computed predictions: pass predictions dict mapping bar index→change_pct
2. On-the-fly model: pass a callable that returns predicted_change_pct for a bar
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent
from core.ids import new_id
from domain.common.enum_types import OrderSide, OrderType


class MlSignalStrategy(BaseStrategy):
    """Trade based on ML-predicted price change percentage.

    Args:
        instrument_id: TSE instrument symbol (e.g. "فولاد")
        buy_threshold: Buy when predicted_change_pct >= this value (default 1.0%)
        sell_threshold: Sell when predicted_change_pct <= this value (default -1.0%)
        enable_short: Allow short selling (default False)
        predictions: Pre-computed dict of {bar_index: predicted_change_pct}
        predictor_fn: Callable that takes a bar dict and returns predicted_change_pct
        sizing_method: Position sizing method ("fixed" or "percent")
        sizing_value: Size of each position
    """

    def __init__(
        self,
        instrument_id: str = "",
        buy_threshold: float = 1.0,
        sell_threshold: float = -1.0,
        enable_short: bool = False,
        predictions: dict[int, float] | None = None,
        predictor_fn: Callable[[dict[str, Any]], float] | None = None,
        sizing_method: str = "fixed",
        sizing_value: float = 1000.0,
    ) -> None:
        super().__init__(
            name=f"MlSignal_{buy_threshold}_{sell_threshold}",
            sizing_method=sizing_method,
            sizing_value=sizing_value,
        )
        self.instrument_id = instrument_id
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self.enable_short = enable_short
        self.predictions = predictions or {}
        self.predictor_fn = predictor_fn
        self._bar_index = 0
        self._position = 0  # 0 = flat, 1 = long, -1 = short

    def _get_predicted_change(self, bar: dict[str, Any]) -> float | None:
        """Get predicted_change_pct for current bar from pre-computed predictions or predictor_fn."""
        # Try pre-computed predictions dict
        pct = self.predictions.get(self._bar_index)
        if pct is not None:
            return pct

        # Try predictor function
        if self.predictor_fn is not None:
            try:
                return self.predictor_fn(bar)
            except Exception:
                return None

        # Try embedded prediction in the bar data (from pre-processing)
        bar_pred = bar.get("predicted_change_pct")
        if bar_pred is not None:
            return float(bar_pred)

        return None

    def on_bar(self, bar: dict[str, Any]) -> list[OrderEvent]:
        price = bar.get("close", 0)
        if price <= 0:
            self._bar_index += 1
            return []

        predicted_change = self._get_predicted_change(bar)
        self._bar_index += 1

        if predicted_change is None:
            return []

        orders: list[OrderEvent] = []

        # BUY signal: predicted change >= buy_threshold
        if predicted_change >= self.buy_threshold and self._position <= 0:
            qty = self._compute_quantity(price)
            orders.append(
                OrderEvent(
                    instrument_id=self.instrument_id,
                    side=OrderSide.BUY,
                    quantity=qty,
                    price=price,
                    order_type=OrderType.MARKET,
                    order_id=new_id("ord"),
                )
            )
            self._position = 1

        # SELL signal: predicted change <= sell_threshold
        elif predicted_change <= self.sell_threshold:
            if self._position > 0:
                # Close long position
                qty = self._compute_quantity(price)
                orders.append(
                    OrderEvent(
                        instrument_id=self.instrument_id,
                        side=OrderSide.SELL,
                        quantity=qty,
                        price=price,
                        order_type=OrderType.MARKET,
                        order_id=new_id("ord"),
                    )
                )
                self._position = 0 if not self.enable_short else -1
            elif self.enable_short and self._position == 0:
                # Open short position
                qty = self._compute_quantity(price)
                orders.append(
                    OrderEvent(
                        instrument_id=self.instrument_id,
                        side=OrderSide.SELL,
                        quantity=qty,
                        price=price,
                        order_type=OrderType.MARKET,
                        order_id=new_id("ord"),
                    )
                )
                self._position = -1

        # Close position if prediction is near zero (neutral zone)
        elif -0.5 < predicted_change < 0.5 and self._position != 0:
            side = OrderSide.SELL if self._position > 0 else OrderSide.BUY
            qty = self._compute_quantity(price)
            orders.append(
                OrderEvent(
                    instrument_id=self.instrument_id,
                    side=side,
                    quantity=qty,
                    price=price,
                    order_type=OrderType.MARKET,
                    order_id=new_id("ord"),
                )
            )
            self._position = 0

        return orders

    def reset(self) -> None:
        self._bar_index = 0
        self._position = 0
