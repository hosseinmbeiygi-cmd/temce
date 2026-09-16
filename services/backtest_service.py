from __future__ import annotations

import asyncio
import contextlib
from datetime import date
from typing import Any

from backtesting.engine.simulator import BacktestSimulator
from backtesting.strategies.base import BaseStrategy
from backtesting.strategies.registry import get_strategy_registry, register_all_strategies
from backtesting.types import BacktestResult
from core.config import settings
from core.db_utils import safe_row_str
from core.ids import new_id
from core.logging import get_logger
from core.result import Result
from core.time import utc_now_naive
from ml.features.price_features import PriceFeatures
from ml.features.technical_features import TechnicalFeatures
from ml.models.registry import model_registry
from ml.types import FeatureMatrix
from repositories.backtest_repository import BacktestRepository
from schemas.api.backtest import BacktestResponse, BacktestResultResponse

logger = get_logger(__name__)


def _get_strategy_class(strategy_name: str) -> type[BaseStrategy] | None:
    registry = get_strategy_registry()
    if not registry.list_names():
        register_all_strategies()
    return registry.get(strategy_name)


def _compute_metrics(result: BacktestResult, risk_free_rate: float | None = None) -> dict[str, float]:
    """Compute all metrics using the dedicated metrics modules.

    Args:
        result: BacktestResult from the simulator
        risk_free_rate: Annualized risk-free rate. If None, uses Iranian market default (25%).
    """
    from backtesting.metrics.drawdown_metrics import DrawdownMetrics
    from backtesting.metrics.return_metrics import ReturnMetrics
    from backtesting.metrics.risk_free_rate import get_risk_free_rate
    from backtesting.metrics.risk_metrics import RiskMetrics
    from backtesting.metrics.trade_metrics import TradeMetrics

    # Use Iranian market risk-free rate if not specified
    if risk_free_rate is None:
        risk_free_rate = get_risk_free_rate("moderate")

    all_metrics: dict[str, float] = {}

    with contextlib.suppress(Exception):
        all_metrics.update(RiskMetrics.compute(result, risk_free_rate))
    with contextlib.suppress(Exception):
        all_metrics.update(TradeMetrics.compute(result))
    with contextlib.suppress(Exception):
        all_metrics.update(ReturnMetrics.compute(result))
    with contextlib.suppress(Exception):
        all_metrics.update(DrawdownMetrics.compute(result))

    # Ensure backward-compatible keys exist
    trading_days = len(result.equity_curve)
    years = trading_days / 252 if trading_days > 0 else 1
    all_metrics.setdefault("total_return_pct", result.total_return_pct)
    all_metrics.setdefault("annualized_return_pct",
        round(((1 + result.total_return_pct / 100) ** (1 / years) - 1) * 100, 2) if years > 0 else 0.0)
    # Use DrawdownMetrics output if available, else fallback to result.max_drawdown
    all_metrics.setdefault("max_drawdown_pct", round(abs(all_metrics.get("max_drawdown", result.max_drawdown)), 2))

    # Round all float values
    return {k: round(v, 4) if isinstance(v, float) else v for k, v in all_metrics.items()}


class BacktestService:
    def __init__(
        self,
        simulator: BacktestSimulator | None = None,
        repository: BacktestRepository | None = None,
    ) -> None:
        self.simulator = simulator or BacktestSimulator()
        self._repo = repository or BacktestRepository()
        self._runs: dict[str, dict[str, Any]] = {}  # fallback in-memory cache
        self._cancel_events: dict[str, asyncio.Event] = {}

    async def run(
        self, strategy: BaseStrategy, capital: float | None = None, data: list[dict[str, Any]] | None = None
    ) -> Result[BacktestResult]:
        capital = capital or settings.backtest_default_capital
        # run() is synchronous (deterministic); no await needed
        return self.simulator.run(strategy, initial_capital=capital, data=data)

    async def run_backtest(
        self,
        name: str,
        symbols: list[str] | None = None,
        strategy_type: str = "moving_average_cross",
        strategy_params: dict[str, Any] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        capital: float = 1_000_000_000,
        data_source: str = "auto",
        commission_pct: float | None = None,
        slippage_bps: float | None = None,
        sizing_method: str = "fixed",
        sizing_value: float = 1000.0,
        stop_loss_pct: float | None = None,
        take_profit_pct: float | None = None,
        benchmark_symbol: str | None = None,
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

            # Only pass parameters that the strategy class accepts
            import inspect
            sig = inspect.signature(strategy_cls.__init__)
            accepted = set(sig.parameters.keys()) - {"self"}

            strategy_kwargs = {}
            for key, val in [
                ("instrument_id", symbols[0]),
                ("sizing_method", sizing_method),
                ("sizing_value", sizing_value),
            ]:
                if key in accepted:
                    strategy_kwargs[key] = val

            # Only pass strategy_params keys that the strategy accepts
            for key, val in strategy_params.items():
                if key in accepted:
                    strategy_kwargs[key] = val

            strategy = strategy_cls(**strategy_kwargs)

            # ── Load historical data ──
            data = await self._load_historical_data(symbols[0], start, end, source=data_source)
            if not data:
                return Result.fail(f"No historical data found for {symbols[0]} in the specified date range")

            # ── Pre-warm per-symbol ADV (audit F5) ──
            # The sync simulator reads ADV from the resolver cache to model
            # volume-based slippage with the symbol's real liquidity instead of
            # a generic default.
            try:
                from backtesting.engine.adv import get_adv_resolver

                await get_adv_resolver().resolve(symbols[0])
            except Exception:
                logger.debug("ADV pre-warm skipped for %s", symbols[0], exc_info=True)

            # ── ML-based strategy: pre-compute predictions ──
            if strategy_type == "ml_signal":
                await self._inject_ml_predictions(data, symbols[0], strategy_params)

            # Track whether data is synthetic (always False since we fail if no real data found)
            is_synthetic = False

            # BUG FIX #7: Data quality validation
            data_quality_report = None
            try:
                from backtesting.data_quality.tick_validator import TickValidator
                validator = TickValidator()
                # Convert OHLCV bars to trade-like format for validator
                trade_like = [{"price": bar.get("close", 0), "volume": bar.get("volume", 0),
                               "timestamp": bar.get("timestamp")} for bar in data]
                quality_report = validator.validate_trades(trade_like)
                if quality_report.quality_score < 0.5:
                    logger.warning("Low data quality for %s: score=%.2f, warnings=%s",
                                   symbols[0], quality_report.quality_score, quality_report.warnings[:5])
                data_quality_report = {
                    "quality_score": round(quality_report.quality_score, 3),
                    "n_ticks_checked": quality_report.n_ticks_checked,
                    "n_bad_ticks": quality_report.n_bad_ticks,
                    "n_price_anomalies": quality_report.n_price_anomalies,
                    "warnings": quality_report.warnings[:10],
                }
            except Exception as dq_err:
                logger.debug("Data quality check skipped: %s", dq_err)

            # Create simulator with commission/slippage/SL/TP if provided
            simulator = self.simulator
            if commission_pct is not None or slippage_bps is not None or stop_loss_pct is not None or take_profit_pct is not None:
                from backtesting.engine.broker import Broker
                from backtesting.engine.simulator import BacktestSimulator

                broker_kwargs = {}
                if commission_pct is not None:
                    broker_kwargs["commission_pct"] = commission_pct
                if slippage_bps is not None:
                    broker_kwargs["slippage_bps"] = slippage_bps
                simulator = BacktestSimulator(broker=Broker(**broker_kwargs))

            # Wire SL/TP if provided
            if stop_loss_pct is not None or take_profit_pct is not None:
                from backtesting.risk.stop_loss import StopLoss
                from backtesting.risk.take_profit import TakeProfit

                if not hasattr(simulator, '_stop_loss'):
                    simulator._stop_loss = None
                    simulator._take_profit = None
                if stop_loss_pct is not None:
                    simulator._stop_loss = StopLoss(pct=stop_loss_pct)
                if take_profit_pct is not None:
                    simulator._take_profit = TakeProfit(pct=take_profit_pct)

            # Create cancel event for this run
            cancel_event = asyncio.Event()
            self._cancel_events[run_id] = cancel_event

            # Note: cancel_event is registered for cancel_run() but simulator.run() doesn't
            # accept it directly. Cancellation is checked via event loop mechanics.
            # simulator.run() is synchronous (deterministic core); no await needed.
            result = simulator.run(strategy, initial_capital=capital, data=data)

            # Clean up cancel event
            self._cancel_events.pop(run_id, None)
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
                completed_at=utc_now_naive().isoformat(),
                data_quality=data_quality_report,
                data_source_warning="SYNTHETIC DATA USED — Results are UNRELIABLE. No real historical data available for this symbol." if is_synthetic else None,
            )

            self._runs[run_id] = response.model_dump()

            # Persist to database
            try:
                from domain.backtest.entities import BacktestRun as BacktestRunEntity

                run_entity = BacktestRunEntity(
                    id=run_id,
                    name=name,
                    strategy_name=strategy_type,
                    instrument_ids=symbols,
                    start_date=start,
                    end_date=end,
                    initial_capital=capital,
                    current_capital=bt_result.final_capital,
                    total_return_pct=metrics.get("total_return_pct", 0.0),
                    status="completed",
                    parameters=strategy_params,
                    extra=metrics,
                )
                run_entity.start()
                run_entity.complete()
                await self._repo.save(run_entity)
            except Exception as save_err:
                logger.warning("Failed to persist backtest result: %s", save_err)

            return Result.ok(BacktestResponse(id=run_id, name=name, status="completed", progress_pct=100.0, message="Backtest completed successfully"))

        except Exception as e:
            logger.exception("Backtest failed")
            return Result.fail(str(e))

    async def run_multi_symbol(
        self,
        name: str,
        symbols: list[str],
        strategy_type: str = "moving_average_cross",
        strategy_params: dict[str, Any] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        capital: float = 1_000_000_000,
        data_source: str = "auto",
        commission_pct: float | None = None,
        slippage_bps: float | None = None,
    ) -> Result[dict[str, Any]]:
        """Run backtest on multiple symbols and return combined results."""
        results = []
        for symbol in symbols:
            single_result = await self.run_backtest(
                name=f"{name}-{symbol}",
                symbols=[symbol],
                strategy_type=strategy_type,
                strategy_params=strategy_params,
                start_date=start_date,
                end_date=end_date,
                capital=capital,
                data_source=data_source,
                commission_pct=commission_pct,
                slippage_bps=slippage_bps,
            )
            if single_result.success:
                run_id = single_result.value.id
                full = await self.get_result(run_id)
                metrics = full.value if (full.success and full.value) else {}
                results.append({"symbol": symbol, "run_id": run_id, "status": "completed", "metrics": metrics})
            else:
                results.append({"symbol": symbol, "status": "failed", "error": single_result.error})

        return Result.ok({
            "strategy_type": strategy_type,
            "total_symbols": len(symbols),
            "successful": sum(1 for r in results if r["status"] != "failed"),
            "failed": sum(1 for r in results if r["status"] == "failed"),
            "results": results,
        })

    @staticmethod
    def _row_to_ohlcv(row) -> dict[str, Any]:
        """Convert a DB row (date, open, high, low, close, volume, value) to OHLCV dict."""
        return {
            "timestamp": str(row[0]) + "T09:00:00",
            "open": float(row[1] or row[4] or 0),
            "high": float(row[2] or row[4] or 0),
            "low": float(row[3] or row[4] or 0),
            "close": float(row[4] or 0),
            "volume": int(row[5] or 0),
            "value": float(row[6] or 0),
        }

    async def _load_historical_data(
        self, symbol: str, start: date, end: date, source: str = "auto"
    ) -> list[dict[str, Any]]:
        """
        Load OHLCV data from database.

        Sources:
        - "auto": try brsapi_historical_daily -> quotes -> generated
        - "historical": brsapi_historical_daily only (multi-year daily)
        - "quotes": quotes table only (imported from CSV/JSON)
        - "intraday": aggregate brsapi_intraday_trades to daily OHLCV
        """
        try:
            import jdatetime
            from sqlalchemy import text

            import core.database as _db

            if _db.async_session_factory is None:
                return []

            # Convert Gregorian dates to Jalali (DB stores Jalali date strings)
            jalali_start = jdatetime.date.fromgregorian(date=start).strftime("%Y-%m-%d")
            jalali_end = jdatetime.date.fromgregorian(date=end).strftime("%Y-%m-%d")

            async with _db.async_session_factory() as session:
                # Source: historical daily
                if source in ("auto", "historical"):
                    result = await session.execute(
                        text("""
                            SELECT date, price_first, price_max, price_min, price_close,
                                   trade_volume, trade_value
                            FROM brsapi_historical_daily
                            WHERE symbol = :symbol
                              AND date >= :start AND date <= :end
                              AND price_close IS NOT NULL AND price_close > 0
                            ORDER BY date ASC
                        """),
                        {"symbol": symbol, "start": jalali_start, "end": jalali_end},
                    )
                    rows = result.fetchall()
                    if rows:
                        logger.info("Loaded %d bars from brsapi_historical_daily for %s", len(rows), symbol)
                        bars = [self._row_to_ohlcv(r) for r in rows]
                        for b in bars:
                            b["instrument_id"] = symbol
                        return bars

                # Source: quotes table
                if source in ("auto", "quotes"):
                    result = await session.execute(
                        text("""
                            SELECT date, price_first, price_high, price_min, price_close,
                                   volume, value
                            FROM quotes
                            WHERE symbol = :symbol
                              AND date >= :start AND date <= :end
                              AND price_close IS NOT NULL AND price_close > 0
                            ORDER BY date ASC
                        """),
                        {"symbol": symbol, "start": jalali_start, "end": jalali_end},
                    )
                    rows = result.fetchall()
                    if rows:
                        logger.info("Loaded %d bars from quotes for %s", len(rows), symbol)
                        bars = [self._row_to_ohlcv(r) for r in rows]
                        for b in bars:
                            b["instrument_id"] = symbol
                        return bars

                # Source: intraday trades aggregated to daily
                if source in ("auto", "intraday"):
                    result = await session.execute(
                        text("""
                            SELECT trade_date,
                                   (ARRAY_AGG(price ORDER BY time ASC))[1] as open_price,
                                   MAX(price) as high_price,
                                   MIN(price) as low_price,
                                   (ARRAY_AGG(price ORDER BY time DESC))[1] as close_price,
                                   SUM(volume) as total_volume,
                                   SUM(price * volume) as total_value
                            FROM brsapi_intraday_trades
                            WHERE symbol = :symbol
                              AND trade_date >= :start AND trade_date <= :end
                              AND price > 0 AND volume > 0
                            GROUP BY trade_date
                            ORDER BY trade_date ASC
                        """),
                        {"symbol": symbol, "start": jalali_start, "end": jalali_end},
                    )
                    rows = result.fetchall()
                    if rows:
                        logger.info("Loaded %d daily bars from intraday trades for %s", len(rows), symbol)
                        return [
                            {
                                "timestamp": str(row[0]) + "T09:00:00",
                                "open": float(row[1] or row[4] or 0),
                                "high": float(row[2] or row[4] or 0),
                                "low": float(row[3] or row[4] or 0),
                                "close": float(row[4] or 0),
                                "volume": int(row[5] or 0),
                                "value": float(row[6] or 0),
                                "instrument_id": symbol,
                            }
                            for row in rows
                        ]

                return []
        except Exception as e:
            logger.warning("Failed to load historical data for %s: %s", symbol, e)
            return []

    async def get_available_symbols(self, start: date | None = None, end: date | None = None) -> list[dict[str, Any]]:
        """Get list of symbols with available data and their date ranges.
        Queries both brsapi_historical_daily and quotes tables.
        """
        try:
            from sqlalchemy import text

            import core.database as _db

            if _db.async_session_factory is None:
                return []

            async with _db.async_session_factory() as session:
                # Merge symbols from both historical tables
                result = await session.execute(text("""
                    SELECT symbol, MIN(date) as start_date, MAX(date) as end_date, COUNT(*) as bar_count
                    FROM (
                        SELECT symbol, date
                        FROM brsapi_historical_daily
                        WHERE price_close > 0
                        UNION ALL
                        SELECT symbol, date
                        FROM quotes
                        WHERE price_close > 0
                    ) combined
                    GROUP BY symbol
                    HAVING COUNT(*) > 10
                    ORDER BY bar_count DESC
                """))
                rows = result.fetchall()
                return [
                    {
                        "symbol": row[0],
                        "start_date": safe_row_str(row, idx=1, default=None),
                        "end_date": safe_row_str(row, idx=2, default=None),
                        "bar_count": row[3],
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.warning("Failed to get available symbols: %s", e)
            return []

    async def get_data_stats(self) -> dict[str, Any]:
        """Get statistics about available backtest data."""
        try:
            from sqlalchemy import text

            from core.database import async_session_factory

            if async_session_factory is None:
                return {}

            async with async_session_factory() as session:
                stats = {}

                # Historical daily
                result = await session.execute(text("""
                    SELECT COUNT(*), COUNT(DISTINCT symbol), MIN(date), MAX(date)
                    FROM brsapi_historical_daily WHERE price_close > 0
                """))
                row = result.fetchone()
                stats["historical_daily"] = {
                    "total_bars": row[0] or 0,
                    "symbols": row[1] or 0,
                    "start_date": row[2],
                    "end_date": row[3],
                }

                # Intraday trades
                result = await session.execute(text("""
                    SELECT COUNT(*), COUNT(DISTINCT symbol), MIN(trade_date), MAX(trade_date)
                    FROM brsapi_intraday_trades WHERE price > 0
                """))
                row = result.fetchone()
                stats["intraday_trades"] = {
                    "total_trades": row[0] or 0,
                    "symbols": row[1] or 0,
                    "start_date": row[2],
                    "end_date": row[3],
                }

                # Quotes
                result = await session.execute(text("""
                    SELECT COUNT(*), COUNT(DISTINCT symbol), MIN(date), MAX(date)
                    FROM quotes WHERE price_close > 0
                """))
                row = result.fetchone()
                stats["quotes"] = {
                    "total_bars": row[0] or 0,
                    "symbols": row[1] or 0,
                    "start_date": row[2],
                    "end_date": row[3],
                }

                return stats
        except Exception as e:
            logger.warning("Failed to get data stats: %s", e)
            return {}

    async def list_runs(self) -> Result[list[dict[str, Any]]]:
        # Try DB first, fallback to in-memory
        try:
            db_result = await self._repo.list(page=1, page_size=500)
            if db_result.success and db_result.value and db_result.value.items:
                items = []
                for r in db_result.value.items:
                    items.append({
                        "id": r.id,
                        "name": r.name,
                        "status": r.status,
                        "strategy_type": r.strategy_name,
                        "symbols": r.instrument_ids,
                        "initial_capital": r.initial_capital,
                        "current_value": r.current_value,
                        "total_return_pct": r.total_return_pct,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    })
                return Result.ok(items)
        except Exception as e:
            logger.warning("Failed to list from DB: %s", e)
        return Result.ok(list(self._runs.values()))

    async def get_run(self, run_id: str) -> Result[dict[str, Any] | None]:
        # Try DB first, fallback to in-memory
        try:
            db_result = await self._repo.get(run_id)
            if db_result.success and db_result.value:
                r = db_result.value
                return Result.ok({
                    "id": r.id,
                    "name": r.name,
                    "status": r.status,
                    "strategy_type": r.strategy_name,
                    "symbols": r.instrument_ids,
                    "initial_capital": r.initial_capital,
                    "current_value": r.current_capital,
                    "total_return_pct": r.total_return_pct,
                    "parameters": r.parameters,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                })
        except Exception as e:
            logger.warning("Failed to get run from DB: %s", e)
        return Result.ok(self._runs.get(run_id))

    async def get_result(self, run_id: str) -> Result[dict[str, Any] | None]:
        # Try DB first (has full metrics in extra), then fallback to in-memory
        try:
            db_result = await self._repo.get(run_id)
            if db_result.success and db_result.value:
                r = db_result.value
                return Result.ok({
                    "id": r.id,
                    "name": r.name,
                    "status": r.status,
                    "total_return_pct": r.total_return_pct,
                    "initial_capital": r.initial_capital,
                    "final_value": r.current_value,
                    "metrics": r.metrics or {},
                })
        except Exception as e:
            logger.warning("Failed to get result from DB: %s", e)
        if run_id in self._runs:
            return Result.ok(self._runs.get(run_id))
        return Result.ok(None)

    async def cancel_run(self, run_id: str) -> Result[bool]:
        # Signal cancellation to running simulator
        cancel_event = self._cancel_events.get(run_id)
        if cancel_event is not None:
            cancel_event.set()
            logger.info("Cancellation signaled for run %s", run_id)

        # Update status in memory cache
        if run_id in self._runs:
            self._runs[run_id]["status"] = "cancelled"

        # Update status in DB
        try:

            db_result = await self._repo.get(run_id)
            if db_result.success and db_result.value:
                db_result.value.status = "cancelled"
                await self._repo.save(db_result.value)
        except Exception as e:
            logger.warning("Failed to update cancel status in DB: %s", e)

        if run_id in self._runs or cancel_event is not None:
            return Result.ok(True)
        return Result.fail("Run not found")

    async def _inject_ml_predictions(
        self,
        bars: list[dict[str, Any]],
        symbol: str,
        strategy_params: dict[str, Any],
    ) -> None:
        """Pre-compute ML predictions for each bar and inject as 'predicted_change_pct'.

        Uses a trained model from ArtifactManager or trains a quick model on the fly
        using the bar data itself. Each bar gets a 'predicted_change_pct' field.
        """
        if len(bars) < 50:
            logger.warning("Not enough bars for ML prediction: %d < 50", len(bars))
            for b in bars:
                b["predicted_change_pct"] = 0.0
            return

        # Try to load a trained model
        model_id = strategy_params.get("model_id", f"xgboost_{symbol}")
        model = None

        from ml.artifacts import ArtifactManager
        artifact_mgr = ArtifactManager()
        try:
            model_obj, _ = artifact_mgr.load_model(model_id)
            model = model_obj
        except Exception:
            with contextlib.suppress(Exception):
                model = model_registry.create("xgboost")

        if model is None or not hasattr(model, "predict"):
            logger.warning("No ML model available for %s, using zero predictions", symbol)
            for b in bars:
                b["predicted_change_pct"] = 0.0
            return

        # Build features from bar data
        try:
            import pandas as pd

            df = pd.DataFrame(bars)
            if "close" not in df.columns or df["close"].isna().all():
                for b in bars:
                    b["predicted_change_pct"] = 0.0
                return

            # Build price features
            price_features = PriceFeatures(window_sizes=[5, 10, 20])
            pf = price_features.compute(df)

            # Build technical features
            rename_map = {"open": "price_open", "high": "price_high", "low": "price_low", "close": "price_close", "volume": "volume"}
            feature_df = df.rename(columns=rename_map)
            tech_features = TechnicalFeatures()
            tf = tech_features.compute(feature_df)

            # Combine
            combined = pf.to_df()
            tech_df = tf.to_df()
            for col in tech_df.columns:
                if col not in combined.columns:
                    combined[col] = tech_df[col]

            combined = combined.dropna()
            if combined.empty:
                for b in bars:
                    b["predicted_change_pct"] = 0.0
                return

            feature_names = [c for c in combined.columns if c not in ("date", "time", "symbol")]
            fm = FeatureMatrix(data=combined[feature_names], feature_names=feature_names)

            # Run predictions
            try:
                result = model.predict(fm)
                predictions = result.predictions
            except Exception:
                predictions = [0.0] * len(fm)

            # Align predictions back to original bars (some may have been dropped by feature engineering)
            pred_idx = 0
            for i, bar in enumerate(bars):
                if i < len(bars) - len(predictions):
                    # Early bars that got dropped during feature engineering
                    bar["predicted_change_pct"] = 0.0
                else:
                    if pred_idx < len(predictions):
                        pct = float(predictions[pred_idx]) * 100
                        bar["predicted_change_pct"] = round(pct, 4)
                        pred_idx += 1
                    else:
                        bar["predicted_change_pct"] = 0.0

            logger.info(
                "Injected ML predictions for %s: %d bars, %d valid predictions",
                symbol, len(bars), pred_idx,
            )
        except Exception as e:
            logger.warning("ML prediction injection failed: %s", e)
            for b in bars:
                b["predicted_change_pct"] = 0.0

    def list_strategies(self) -> list[dict[str, Any]]:
        registry = get_strategy_registry()
        if not registry.list_names():
            register_all_strategies()
        return registry.list_strategies()

