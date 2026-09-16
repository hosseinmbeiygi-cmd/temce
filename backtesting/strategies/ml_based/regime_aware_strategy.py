from __future__ import annotations

import contextlib
from typing import Any

from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent


class RegimeAwareStrategy(BaseStrategy):
    def __init__(
        self,
        regime_model=None,
        bull_strategy: BaseStrategy | None = None,
        bear_strategy: BaseStrategy | None = None,
        instrument_id: str = "",
    ) -> None:
        super().__init__(name="RegimeAware")
        self.regime_model = regime_model
        self.bull_strategy = bull_strategy
        self.bear_strategy = bear_strategy
        self.instrument_id = instrument_id
        self._current_regime: str = "neutral"
        self._position = 0

    def _detect_regime(self, bar: dict[str, Any]) -> str:
        if self.regime_model is not None and hasattr(self.regime_model, "predict"):
            features = [bar.get(k, 0.0) for k in ["close", "volume", "returns_20d", "volatility_20d"]]
            with contextlib.suppress(Exception):
                regime = self.regime_model.predict([features])[0]
                return {0: "bear", 1: "bull", 2: "neutral"}.get(int(regime), "neutral")
        returns = bar.get("returns_20d", 0)
        vol = bar.get("volatility_20d", 0.02)
        if returns > 0.05 and vol < 0.03:
            return "bull"
        elif returns < -0.05:
            return "bear"
        return "neutral"

    def on_bar(self, bar: dict[str, Any]) -> list[OrderEvent]:
        self._current_regime = self._detect_regime(bar)
        price = bar.get("close", 0)
        if price <= 0:
            return []
        if self._current_regime == "bull" and self.bull_strategy:
            return self.bull_strategy.on_bar(bar)
        elif self._current_regime == "bear" and self.bear_strategy:
            return self.bear_strategy.on_bar(bar)
        return []

    def reset(self) -> None:
        self._current_regime = "neutral"
        self._position = 0
        if self.bull_strategy:
            self.bull_strategy.reset()
        if self.bear_strategy:
            self.bear_strategy.reset()
