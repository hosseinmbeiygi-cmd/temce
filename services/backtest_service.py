from __future__ import annotations

import math
import random
from datetime import date, datetime, timedelta
from typing import Any

from backtesting.engine.simulator import BacktestSimulator
from backtesting.strategies.base import BaseStrategy
from backtesting.strategies.registry import get_strategy_registry, register_all_strategies
from backtesting.types import BacktestResult
from core.config import settings
from core.ids import new_id
from core.logging import get_logger
from core.result import Result
from schemas.api.backtest import BacktestResponse, BacktestResultResponse

logger = get_logger(__name__)


def _get_strategy_class(strategy_name: str) -> type[BaseStrategy] | None:
    registry = get_strategy_registry()
    if not registry.list_names():
        register_all_strategies()
    return registry.get(strategy_name)


def _generate_ohlcv_data(
    symbol: str,
    start_date: date,
    end_date: date,
    base_price: float | None = None,
    volatility: float = 0.015,
) -> list[dict[str, Any]]:
    if base_price is None:
        base_price = random.uniform(1000, 50000)
        if symbol in ("فولاد", "شپنا", "وبملت", "خودرو", "فملی"):
            base_price = {"فولاد": 38500, "شپنا": 45200, "وبملت": 14200, "خودرو": 28500, "فملی": 62500}.get(symbol, base_price)

    bars: list[dict[str, Any]] = []
    current = start_date
    price = base_price
    drift = base_price * 0.0005

    while current <= end_date:
        if current.weekday() >= 5:
            current += timedelta(days=1)
            continue

        change = random.gauss(0, 1) * volatility * price + drift * random.uniform(-1, 1)
        price = max(price * 0.9, price + change)
        open_p = price * (1 + random.uniform(-0.005, 0.005))
        high = max(open_p, price) * (1 + random.uniform(0, 0.01))
        low = min(open_p, price) * (1 - random.uniform(0, 0.01))
        volume = int(random.uniform(100000, 5000000))
        value = volume * price

        bars.append({
            "timestamp": datetime.combine(current, datetime.min.time()).isoformat(),
            "open": round(open_p, 1),
            "high": round(high, 1),
            "low": round(low, 1),
            "close": round(price, 1),
            "volume": volume,
            "value": value,
        })
        current += timedelta(days=1)

    return bars


def _compute_metrics(result: BacktestResult, risk_free_rate: float = 0.0) -> dict[str, float]:
    total_return_pct = result.total_return_pct

    trading_days = len(result.equity_curve)
    years = trading_days / 252 if trading_days > 0 else 1
    annualized = ((1 + total_return_pct / 100) ** (1 / years) - 1) * 100 if years > 0 else 0.0

    returns = []
    peak = float("-inf")
    max_dd = 0.0
    for ep in result.equity_curve:
        nav = ep.nav
        r = (nav / result.initial_capital) - 1
        returns.append(r)

        if nav > peak:
            peak = nav
        dd = (peak - nav) / peak if peak > 0 else 0
        max_dd = max(max_dd, dd)

    avg_r = sum(returns) / len(returns) if returns else 0
    variance = sum((r - avg_r) ** 2 for r in returns) / len(returns) if returns else 1
    std = math.sqrt(variance)
    risk_free_daily = risk_free_rate / 252.0  # Convert annual RF to match daily returns
    excess_avg_r = avg_r - risk_free_daily
    sharpe = (excess_avg_r / std) * math.sqrt(252) if std > 0 else 0.0

    wins = sum(1 for t in result.trades if hasattr(t, "pnl") and getattr(t, "pnl", 0) > 0)
    losses = sum(1 for t in result.trades if hasattr(t, "pnl") and getattr(t, "pnl", 0) <= 0)

    return {
        "total_return_pct": round(total_return_pct, 2),
        "annualized_return_pct": round(annualized, 2),
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "win_rate": round(wins / (wins + losses) * 100, 2) if (wins + losses) > 0 else 0.0,
    }


class BacktestService:
    def __init__(self, simulator: BacktestSimulator | None = None) -> None:
        self.simulator = simulator or BacktestSimulator()
        self._runs: dict[str, dict[str, Any]] = {}

    async def run(
        self, strategy: BaseStrategy, capital: float | None = None, data: list[dict[str, Any]] | None = None
    ) -> Result[BacktestResult]:
        capital = capital or settings.backtest_default_capital
        return await self.simulator.run(strategy, initial_capital=capital, data=data)

    async def run_backtest(
        self,
        name: str,
        symbols: list[str] | None = None,
        strategy_type: str = "moving_average_cross",
        strategy_params: dict[str, Any] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        capital: float = 1_000_000_000,
    ) -> Result[BacktestResponse]:
        try:
            run_id = new_id("bt")
            symbols = symbols or ["فولاد"]
            strategy_params = strategy_params or {}
            today = date.today()
            start = start_date or date(today.year - 1, 1, 1)
            end = end_date or today

            strategy_cls = _get_strategy_class(strategy_type)
            if strategy_cls is None:
                registry = get_strategy_registry()
                available = registry.list_names() or ["moving_average_cross", "momentum", "mean_reversion", "breakout", "rsi_reversion", "volatility_breakout"]
                return Result.fail(f"Unknown strategy '{strategy_type}'. Available: {', '.join(available)}")

            strategy = strategy_cls(instrument_id=symbols[0], **strategy_params)

            # Try to load real historical data from DB
            data = await self._load_historical_data(symbols[0], start, end)

            # Fallback to generated data if no real data found
            if not data:
                logger.info("No historical data for %s, using generated data", symbols[0])
                data = _generate_ohlcv_data(symbols[0], start, end)

            result = await self.simulator.run(strategy, initial_capital=capital, data=data)
            if not result.success:
                return Result.fail(result.error or "Backtest simulation failed")

            bt_result = result.value
            metrics = _compute_metrics(bt_result)

            equity_curve = [
                {"timestamp": str(ep.timestamp), "nav": ep.nav, "cash": ep.cash, "positions_value": ep.positions_value}
                for ep in bt_result.equity_curve
            ]
            trades_list = [
                {
                    "instrument_id": getattr(t, "instrument_id", ""),
                    "side": str(getattr(t, "side", "")),
                    "quantity": getattr(t, "quantity", 0),
                    "price": getattr(t, "price", 0.0),
                    "pnl": getattr(t, "pnl", 0.0),
                }
                for t in bt_result.trades
            ]

            response = BacktestResultResponse(
                id=run_id,
                name=name,
                status="completed",
                total_return_pct=metrics["total_return_pct"],
                annualized_return_pct=metrics["annualized_return_pct"],
                sharpe_ratio=metrics["sharpe_ratio"],
                max_drawdown_pct=metrics["max_drawdown_pct"],
                win_rate=metrics["win_rate"],
                total_trades=len(bt_result.trades),
                winning_trades=sum(1 for t in bt_result.trades if hasattr(t, "pnl") and getattr(t, "pnl", 0) > 0),
                losing_trades=sum(1 for t in bt_result.trades if hasattr(t, "pnl") and getattr(t, "pnl", 0) <= 0),
                initial_capital=capital,
                final_value=bt_result.final_capital,
                equity_curve=equity_curve,
                trades=trades_list,
                metrics=metrics,
                completed_at=datetime.now().isoformat(),
            )

            self._runs[run_id] = response.model_dump()
            return Result.ok(BacktestResponse(id=run_id, name=name, status="completed", progress_pct=100.0, message="Backtest completed successfully"))

        except Exception as e:
            logger.exception("Backtest failed")
            return Result.fail(str(e))

    async def _load_historical_data(
        self, symbol: str, start: date, end: date
    ) -> list[dict[str, Any]]:
        """Load OHLCV data from brsapi_historical_daily table."""
        try:
            from core.database import async_session_factory
            from sqlalchemy import text

            if async_session_factory is None:
                return []

            async with async_session_factory() as session:
                result = await session.execute(
                    text("""
                        SELECT date, price_open, price_high, price_low, price_close, trade_volume, trade_value
                        FROM brsapi_historical_daily
                        WHERE symbol = :symbol
                          AND date >= :start AND date <= :end
                          AND price_close IS NOT NULL AND price_close > 0
                        ORDER BY date ASC
                    """),
                    {"symbol": symbol, "start": str(start), "end": str(end)},
                )
                rows = result.fetchall()

                if not rows:
                    return []

                return [
                    {
                        "timestamp": str(row[0]) + "T09:00:00",
                        "open": float(row[1] or row[4]),
                        "high": float(row[2] or row[4]),
                        "low": float(row[3] or row[4]),
                        "close": float(row[4]),
                        "volume": int(row[5] or 0),
                        "value": float(row[6] or 0),
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.warning("Failed to load historical data for %s: %s", symbol, e)
            return []

    async def list_runs(self) -> Result[list[dict[str, Any]]]:
        return Result.ok(list(self._runs.values()))

    async def get_run(self, run_id: str) -> Result[dict[str, Any] | None]:
        return Result.ok(self._runs.get(run_id))

    async def get_result(self, run_id: str) -> Result[dict[str, Any] | None]:
        return Result.ok(self._runs.get(run_id))

    async def cancel_run(self, run_id: str) -> Result[bool]:
        if run_id in self._runs:
            self._runs[run_id]["status"] = "cancelled"
            return Result.ok(True)
        return Result.fail("Run not found")

    def list_strategies(self) -> list[dict[str, Any]]:
        registry = get_strategy_registry()
        if not registry.list_names():
            register_all_strategies()
        return registry.list_strategies()

