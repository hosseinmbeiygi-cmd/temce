from __future__ import annotations

from typing import Any

import numpy as np

from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent


class MinimumVarianceStrategy(BaseStrategy):
    def __init__(self, instrument_ids: list[str] | None = None, lookback: int = 252) -> None:
        super().__init__(name="MinVariance")
        self.instrument_ids = instrument_ids or []
        self.lookback = lookback
        self._price_history: dict[str, list[float]] = {}
        self._weights: dict[str, float] = {}

    def on_bar(self, bar: dict[str, Any]) -> list[OrderEvent]:
        for inst_id in self.instrument_ids:
            price = (
                bar.get("close", 0)
                if isinstance(bar.get("close"), (int, float))
                else bar.get(inst_id, {}).get("close", 0)
            )
            if price > 0:
                self._price_history.setdefault(inst_id, []).append(price)
        if len(self._price_history.get(self.instrument_ids[0], [])) < self.lookback:
            return []
        self._optimize_weights()
        return []

    def _optimize_weights(self) -> None:
        prices = np.array([self._price_history[inst][-self.lookback :] for inst in self.instrument_ids])
        returns = np.diff(prices) / np.where(prices[:, :-1] != 0, prices[:, :-1], 1.0)
        cov = np.cov(returns)
        n = len(self.instrument_ids)
        from scipy.optimize import minimize

        def portfolio_vol(w: np.ndarray) -> float:
            return float(np.sqrt(np.dot(w.T, np.dot(cov, w))))

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
        bounds = [(0, 1) for _ in range(n)]
        x0 = np.ones(n) / n
        try:
            result = minimize(portfolio_vol, x0, bounds=bounds, constraints=constraints, method="SLSQP")
            w = np.abs(result.x)
            w = w / w.sum()
        except Exception:
            w = np.ones(n) / n
        self._weights = {inst: float(w[i]) for i, inst in enumerate(self.instrument_ids)}

    def get_weights(self) -> dict[str, float]:
        return dict(self._weights)

    def reset(self) -> None:
        self._price_history.clear()
        self._weights.clear()
