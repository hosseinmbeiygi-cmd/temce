from __future__ import annotations

from domain.backtest.entities import BacktestRun, Order


class BacktestDateRule:
    """Validate that start_date is before end_date."""

    def validate(self, start_date: str, end_date: str) -> bool:
        return start_date < end_date if start_date and end_date else False


class BacktestCapitalRule:
    """Validate that initial capital meets the minimum requirement."""

    def __init__(self, min_capital: float = 0.0) -> None:
        self.min_capital = min_capital

    def validate(self, initial_capital: float) -> bool:
        return initial_capital >= self.min_capital


class BacktestSymbolRule:
    """Validate that the number of symbols doesn't exceed the maximum."""

    def __init__(self, max_symbols: int = 0) -> None:
        self.max_symbols = max_symbols

    def validate(self, symbols: list[str]) -> bool:
        return len(symbols) <= self.max_symbols


class BacktestTimeframeRule:
    """Validate that the timeframe is in the allowed list."""

    def __init__(self, allowed_timeframes: list[str] | None = None) -> None:
        self.allowed_timeframes = allowed_timeframes or []

    def validate(self, timeframe: str) -> bool:
        return timeframe in self.allowed_timeframes


def can_execute_order(order: Order, capital: float) -> bool:
    if order.side.value == "buy":
        return order.price * order.quantity <= capital
    return True


def validate_backtest_dates(start_date: str, end_date: str) -> bool:
    return start_date < end_date if start_date and end_date else False


def validate_initial_capital(capital: float) -> bool:
    return capital > 0


def is_backtest_completed(run: BacktestRun) -> bool:
    return run.status == "completed"


def is_backtest_running(run: BacktestRun) -> bool:
    return run.status == "running"
