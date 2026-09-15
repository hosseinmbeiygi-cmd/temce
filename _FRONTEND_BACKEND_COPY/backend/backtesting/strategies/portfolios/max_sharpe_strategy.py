from __future__ import annotations

from typing import Any

import numpy as np

from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent


class MaxSharpeStrategy(BaseStrategy):
    def __init__(self, instrument_ids: list[str] | None = None, lookback: int = 252) -> None:
        super().__init__(name="MaxSharpe")
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
        returns = np.diff(prices) / prices[:, :-1]
        mean_ret = np.mean(returns, axis=1)
        cov = np.cov(returns)
        n = len(self.instrument_ids)
        best_sharpe = -1e9
        best_w = np.ones(n) / n
        for _ in range(10000):
            w = np.random.dirichlet(np.ones(n))
            port_ret = np.dot(w, mean_ret)
            port_vol = np.sqrt(np.dot(w.T, np.dot(cov, w)))
            sharpe = port_ret / port_vol if port_vol > 0 else 0
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_w = w
        self._weights = {inst: float(best_w[i]) for i, inst in enumerate(self.instrument_ids)}

    def get_weights(self) -> dict[str, float]:
        return dict(self._weights)

    def reset(self) -> None:
        self._price_history.clear()
        self._weights.clear()
