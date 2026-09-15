from __future__ import annotations

from typing import Any

from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent
from core.ids import new_id
from domain.common.enum_types import OrderSide, OrderType


class RankingSignalStrategy(BaseStrategy):
    def __init__(self, model=None, instrument_ids: list[str] | None = None) -> None:
        super().__init__(name="RankingSignal")
        self.model = model
        self.instrument_ids = instrument_ids or []
        self._scores: dict[str, float] = {}
        self._position: dict[str, int] = {}

    def on_bar(self, bar: dict[str, Any]) -> list[OrderEvent]:
        if not self.instrument_ids or self.model is None:
            return []
        orders: list[OrderEvent] = []
        for inst_id in self.instrument_ids:
            features = self._extract_features(bar, inst_id)
            score = self.model.predict([features])[0] if hasattr(self.model, "predict") else 0.0
            self._scores[inst_id] = float(score)
        sorted_inst = sorted(self._scores, key=self._scores.get, reverse=True)
        top_k = sorted_inst[: max(1, len(sorted_inst) // 3)]
        for inst_id in self.instrument_ids:
            price = bar.get("close", 0)
            if price <= 0:
                continue
            if inst_id in top_k and self._position.get(inst_id, 0) <= 0:
                orders.append(
                    OrderEvent(
                        instrument_id=inst_id,
                        side=OrderSide.BUY,
                        quantity=1000,
                        price=price,
                        order_type=OrderType.MARKET,
                        order_id=new_id("ord"),
                    )
                )
                self._position[inst_id] = 1
            elif inst_id not in top_k and self._position.get(inst_id, 0) >= 0:
                orders.append(
                    OrderEvent(
                        instrument_id=inst_id,
                        side=OrderSide.SELL,
                        quantity=1000,
                        price=price,
                        order_type=OrderType.MARKET,
                        order_id=new_id("ord"),
                    )
                )
                self._position[inst_id] = -1
        return orders

    def _extract_features(self, bar: dict[str, Any], instrument_id: str) -> list[float]:
        data = bar.get(instrument_id, bar)
        return [data.get(k, 0.0) for k in ["close", "volume", "open", "high", "low"]]

    def reset(self) -> None:
        self._scores.clear()
        self._position.clear()
