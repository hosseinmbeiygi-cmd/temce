from __future__ import annotations

import pandas as pd

from ml.types import TargetVector


class LabelGenerator:
    def future_return(
        self,
        close_prices: pd.Series,
        horizon: int = 5,
        open_prices: pd.Series | None = None,
    ) -> TargetVector:
        """
        Compute forward return from execution price to exit price.

        By default uses close[t] as entry (legacy behavior). When open_prices
        is provided, uses open[t+1] as entry price to match real execution
        timeline (signal at t executes at open of t+1).

        Args:
            close_prices: Series of close prices (exit prices)
            horizon: Forward horizon in bars
            open_prices: Optional Series of open prices. If provided,
                entry price is open[t+1], exit is close[t+horizon].
                If None, falls back to close[t] entry (legacy).
        """
        if open_prices is not None:
            entry = open_prices.shift(-1)
            exit_price = close_prices.shift(-horizon)
            future_return = (exit_price / entry - 1).dropna()
        else:
            future = close_prices.shift(-horizon) / close_prices - 1
            future_return = future.dropna()
        return TargetVector(data=future_return, name=f"future_return_{horizon}", task_type="regression")

    def binary_direction(
        self,
        close_prices: pd.Series,
        horizon: int = 5,
        open_prices: pd.Series | None = None,
    ) -> TargetVector:
        """
        Compute binary direction from execution price to exit price.

        When open_prices provided, uses open[t+1] as entry price.
        """
        if open_prices is not None:
            entry = open_prices.shift(-1)
            exit_price = close_prices.shift(-horizon)
            direction = (exit_price > entry).astype(int).dropna()
        else:
            future = close_prices.shift(-horizon)
            direction = (future > close_prices).astype(int).dropna()
        return TargetVector(data=direction, name=f"direction_{horizon}", task_type="binary_classification")

    def volatility_regime(self, returns: pd.Series, window: int = 20) -> TargetVector:
        vol = returns.rolling(window).std()
        median = vol.median()
        regime = (vol > median).astype(int)
        return TargetVector(data=regime.dropna(), name="vol_regime", task_type="binary_classification")
