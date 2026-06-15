from __future__ import annotations

from core.exceptions import DomainError


class BacktestError(DomainError):
    def __init__(self, message: str = "Backtest error", code: str = "BACKTEST_ERROR") -> None:
        super().__init__(message=message, code=code)


class InsufficientDataError(BacktestError):
    def __init__(self, message: str = "Insufficient historical data for backtest") -> None:
        super().__init__(message=message, code="INSUFFICIENT_DATA")


class StrategyError(BacktestError):
    def __init__(self, message: str = "Strategy error", strategy: str | None = None) -> None:
        super().__init__(message=message, code="STRATEGY_ERROR")


class OptimizationError(BacktestError):
    def __init__(self, message: str = "Optimization failed") -> None:
        super().__init__(message=message, code="OPTIMIZATION_ERROR")


class OverfittingDetected(BacktestError):
    def __init__(self, message: str = "Potential overfitting detected") -> None:
        super().__init__(message=message, code="OVERFITTING_DETECTED")
