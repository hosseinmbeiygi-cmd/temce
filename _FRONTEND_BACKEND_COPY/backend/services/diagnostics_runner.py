"""
Comprehensive System Diagnostics Runner
=======================================
Checks all symbols across the entire platform:
  1. Data integrity — verifies historical data exists, no gaps, no NaN
  2. Backtest smoke tests — runs representative strategies per symbol
  3. ML model health — checks model availability and prediction validity
  4. Database persistence — stores findings in `diagnostic_runs` and `diagnostic_findings`

Usage:
    python services/diagnostics_runner.py
    python services/diagnostics_runner.py --symbols فولاد,شپنا  # limit to specific symbols
    python services/diagnostics_runner.py --limit 50              # only check first 50 symbols
    python services/diagnostics_runner.py --skip-backtests        # data + ML checks only
"""

from __future__ import annotations

import asyncio
import sys
import time
import traceback
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

# Ensure the project root is on sys.path so all imports resolve
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.logging import get_logger

logger = get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

SMOKE_TEST_BARS = 120  # last N bars to run smoke tests on
MIN_BARS_FOR_BACKTEST = 50  # minimum bars required to run a meaningful backtest
SMOKE_TEST_CAPITAL = 10_000_000  # small capital for smoke tests (10M IRR)
DEFAULT_SYMBOL_LIMIT = 200  # max symbols to check in one run
MAX_CONCURRENT_SYMBOLS = 5  # process symbols concurrently for speed

# Strategy subsets for smoke testing (pulled dynamically from registry at init)
# These are fallback names if registry is unavailable
SMOKE_TEST_STRATEGIES: list[dict[str, Any]] = [
    {"name": "moving_average_cross", "type": "rule_based", "params": {"fast_period": 5, "slow_period": 20}},
    {"name": "momentum", "type": "rule_based", "params": {"lookback": 20}},
    {"name": "mean_reversion", "type": "rule_based", "params": {"lookback": 20}},
    {"name": "breakout", "type": "rule_based", "params": {"lookback": 20}},
    {"name": "half_trend", "type": "rule_based", "params": {}},
    {"name": "ml_signal", "type": "ml_based", "params": {}},
    {"name": "rsi_reversion", "type": "rule_based", "params": {"period": 14}},
    {"name": "squeeze_momentum", "type": "rule_based", "params": {}},
    {"name": "support_resistance", "type": "rule_based", "params": {}},
    {"name": "volatility_breakout", "type": "rule_based", "params": {}},
]


# ── Data classes ─────────────────────────────────────────────────────────────


class DiagnosticFinding:
    """A single finding (issue or success) from the diagnostic run."""

    __slots__ = ("level", "category", "symbol", "message", "details", "strategy", "duration_ms")

    def __init__(
        self,
        level: str,  # CRITICAL | ERROR | WARNING | INFO
        category: str,  # data | backtest | ml | system
        symbol: str,
        message: str,
        details: str = "",
        strategy: str = "",
        duration_ms: float = 0.0,
    ) -> None:
        self.level = level
        self.category = category
        self.symbol = symbol
        self.message = message
        self.details = details
        self.strategy = strategy
        self.duration_ms = duration_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "category": self.category,
            "symbol": self.symbol,
            "message": self.message,
            "details": self.details,
            "strategy": self.strategy,
            "duration_ms": self.duration_ms,
        }


class DiagnosticRunResult:
    """Aggregated results from a full diagnostic run."""

    __slots__ = (
        "run_id",
        "started_at",
        "finished_at",
        "total_symbols",
        "total_findings",
        "critical_count",
        "error_count",
        "warning_count",
        "info_count",
        "findings_by_category",
        "findings",
    )

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.started_at: datetime | None = None
        self.finished_at: datetime | None = None
        self.total_symbols = 0
        self.total_findings = 0
        self.critical_count = 0
        self.error_count = 0
        self.warning_count = 0
        self.info_count = 0
        self.findings_by_category: dict[str, int] = {}
        self.findings: list[DiagnosticFinding] = []

    def add_finding(self, f: DiagnosticFinding) -> None:
        self.findings.append(f)
        self.total_findings += 1
        if f.level == "CRITICAL":
            self.critical_count += 1
        elif f.level == "ERROR":
            self.error_count += 1
        elif f.level == "WARNING":
            self.warning_count += 1
        else:
            self.info_count += 1
        self.findings_by_category[f.category] = self.findings_by_category.get(f.category, 0) + 1

    def summary(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_seconds": (
                (self.finished_at - self.started_at).total_seconds() if self.started_at and self.finished_at else None
            ),
            "total_symbols": self.total_symbols,
            "total_findings": self.total_findings,
            "by_level": {
                "critical": self.critical_count,
                "error": self.error_count,
                "warning": self.warning_count,
                "info": self.info_count,
            },
            "by_category": self.findings_by_category,
            "health": "healthy" if self.critical_count == 0 and self.error_count == 0 else "degraded",
        }


# ── Diagnostics Runner ───────────────────────────────────────────────────────


class DiagnosticsRunner:
    """Orchestrates the full diagnostic pipeline."""

    def __init__(self) -> None:
        self.result = DiagnosticRunResult(run_id=f"diag-{int(time.time() * 1000)}")
        self._registry_loaded = False
        self._strategy_names: list[str] = []
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_SYMBOLS)

    # ── Pipeline ─────────────────────────────────────────────────────────

    async def run(
        self,
        symbol_filter: list[str] | None = None,
        limit: int = DEFAULT_SYMBOL_LIMIT,
        skip_backtests: bool = False,
        skip_ml: bool = False,
    ) -> DiagnosticRunResult:
        """Run the full diagnostic pipeline."""
        self.result.started_at = datetime.now(UTC)

        logger.info(
            "Diagnostic run started: %s (limit=%d, skip_backtests=%s)", self.result.run_id, limit, skip_backtests
        )

        try:
            # Step 1: System health check
            await self._check_system()

            # Step 2: Fetch all symbols
            symbols = await self._fetch_symbols(symbol_filter, limit)
            self.result.total_symbols = len(symbols)
            logger.info("Fetched %d symbols for diagnostics", len(symbols))

            # Step 3: Per-symbol checks (concurrent processing)
            async def _check_symbol(idx: int, sym_info: dict[str, Any]) -> None:
                async with self._semaphore:
                    symbol = sym_info["symbol"]
                    name = sym_info.get("name", "")
                    logger.debug("  [%d/%d] Checking %s (%s)", idx + 1, len(symbols), symbol, name)

                    # 3a: Data integrity (daily + intraday)
                    daily_bars = await self._fetch_history(symbol)
                    intraday_bars = await self._fetch_intraday(symbol)
                    data_ok = self._validate_data(symbol, daily_bars, intraday_bars)

                    # 3b: Backtest smoke tests
                    if data_ok and not skip_backtests:
                        await self._run_smoke_tests(symbol, daily_bars)

                    # 3c: ML model check
                    if not skip_ml:
                        await self._check_ml_model(symbol)

            tasks = [_check_symbol(i, sym) for i, sym in enumerate(symbols)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # Log any unexpected exceptions from per-symbol checks
            for result_exc in results:
                if isinstance(result_exc, BaseException):
                    logger.warning("Symbol check raised unhandled exception: %s", result_exc)

            # Step 4: Cross-cutting checks
            await self._cross_checks()

        except Exception as exc:
            logger.exception("Diagnostic run failed with exception")
            self.result.add_finding(
                DiagnosticFinding(
                    level="CRITICAL",
                    category="system",
                    symbol="__ALL__",
                    message=f"Diagnostic run crashed: {exc}",
                    details=traceback.format_exc(),
                )
            )

        self.result.finished_at = datetime.now(UTC)
        logger.info(
            "Diagnostic run finished: %s — %d findings (%d critical, %d errors)",
            self.result.run_id,
            self.result.total_findings,
            self.result.critical_count,
            self.result.error_count,
        )

        # Persist results
        await self._persist_results()

        return self.result

    # ── System check ─────────────────────────────────────────────────────

    async def _check_system(self) -> None:
        """Verify database connectivity and core services."""
        try:
            from core.database import async_session_factory

            if async_session_factory is None:
                self.result.add_finding(
                    DiagnosticFinding(
                        level="CRITICAL",
                        category="system",
                        symbol="__ALL__",
                        message="Database not initialized — async_session_factory is None",
                        details="Call init_database() before running diagnostics.",
                    )
                )
                return

            async with async_session_factory() as session:
                from sqlalchemy import text

                result = await session.execute(text("SELECT 1"))
                if result.scalar() == 1:
                    self.result.add_finding(
                        DiagnosticFinding(
                            level="INFO",
                            category="system",
                            symbol="__ALL__",
                            message="Database connectivity: OK",
                        )
                    )
        except Exception as exc:
            self.result.add_finding(
                DiagnosticFinding(
                    level="CRITICAL",
                    category="system",
                    symbol="__ALL__",
                    message=f"Database connectivity failed: {exc}",
                    details=traceback.format_exc(),
                )
            )

    # ── Symbol fetching ───────────────────────────────────────────────────

    async def _fetch_symbols(self, symbol_filter: list[str] | None, limit: int) -> list[dict[str, Any]]:
        """Fetch all active symbols from the database."""
        try:
            from sqlalchemy import select

            from core.database import async_session_factory

            async with async_session_factory() as session:
                # Try InstrumentModel first, fall back to SymbolModel
                try:
                    from models.instrument import InstrumentModel

                    query = select(
                        InstrumentModel.symbol,
                        InstrumentModel.name,
                        InstrumentModel.market_type,
                    ).where(InstrumentModel.status == "active")

                    if symbol_filter:
                        query = query.where(InstrumentModel.symbol.in_(symbol_filter))

                    query = query.limit(limit)
                    result = await session.execute(query)
                    rows = result.fetchall()
                    if rows:
                        return [{"symbol": r[0], "name": r[1] or "", "market_type": r[2] or ""} for r in rows]
                except Exception as exc:
                    logger.debug("InstrumentModel fetch failed, trying SymbolModel: %s", exc)

                # Fallback: try SymbolModel (market_data.py)
                from models.market_data import SymbolModel

                query = select(SymbolModel.symbol, SymbolModel.name).limit(limit)
                if symbol_filter:
                    query = query.where(SymbolModel.symbol.in_(symbol_filter))
                result = await session.execute(query)
                rows = result.fetchall()
                return [{"symbol": r[0], "name": r[1] or "", "market_type": ""} for r in rows]

        except Exception as exc:
            self.result.add_finding(
                DiagnosticFinding(
                    level="CRITICAL",
                    category="system",
                    symbol="__ALL__",
                    message=f"Failed to fetch symbols: {exc}",
                    details=traceback.format_exc(),
                )
            )
            return []

    # ── Historical data ───────────────────────────────────────────────────

    async def _fetch_history(self, symbol: str) -> list[dict[str, Any]]:
        """Fetch recent historical bars for a symbol."""
        try:
            from sqlalchemy import desc, select, text

            from core.database import async_session_factory

            async with async_session_factory() as session:
                # Try daily_history table first
                try:
                    from models.market_data import DailyHistoryModel, SymbolModel

                    # Resolve symbol_id
                    sym_result = await session.execute(select(SymbolModel.id).where(SymbolModel.symbol == symbol))
                    sym_id = sym_result.scalar()
                    if sym_id is None:
                        return []

                    # NOTE: daily_history (migration 0001) stores OHLC under the
                    # price_* column family: price_first=open, price_max=high,
                    # price_min=low, price_close=close, trade_volume/trade_value.
                    # There are no open_price/high_price/... columns here.
                    query = (
                        select(
                            DailyHistoryModel.trade_date,
                            DailyHistoryModel.price_first,
                            DailyHistoryModel.price_max,
                            DailyHistoryModel.price_min,
                            DailyHistoryModel.price_close,
                            DailyHistoryModel.trade_volume,
                            DailyHistoryModel.trade_value,
                        )
                        .where(DailyHistoryModel.symbol_id == sym_id)
                        .order_by(desc(DailyHistoryModel.trade_date))
                        .limit(SMOKE_TEST_BARS + 50)
                    )
                    result = await session.execute(query)
                    rows = result.fetchall()
                    if rows:
                        return [
                            {
                                "date": str(r[0]),
                                "open": float(r[1] or 0),
                                "high": float(r[2] or 0),
                                "low": float(r[3] or 0),
                                "close": float(r[4] or 0),
                                "volume": float(r[5] or 0),
                                "value": float(r[6] or 0),
                            }
                            for r in reversed(rows)  # chronological order
                        ]
                except Exception:
                    pass

                # Fallback: try raw SQL on various history tables
                for table_name in ["daily_history", "history_data", "price_history"]:
                    try:
                        result = await session.execute(
                            text(
                                f"SELECT trade_date, price_first, price_max, price_min, "
                                f"price_close, trade_volume, trade_value "
                                f"FROM {table_name} "
                                f"WHERE symbol = :sym OR symbol_id = (SELECT id FROM symbols WHERE symbol = :sym2) "
                                f"ORDER BY trade_date DESC LIMIT :lim"
                            ),
                            {"sym": symbol, "sym2": symbol, "lim": SMOKE_TEST_BARS + 50},
                        )
                        rows = result.fetchall()
                        if rows:
                            return [
                                {
                                    "date": str(r[0]),
                                    "open": float(r[1] or 0),
                                    "high": float(r[2] or 0),
                                    "low": float(r[3] or 0),
                                    "close": float(r[4] or 0),
                                    "volume": float(r[5] or 0),
                                    "value": float(r[6] or 0),
                                }
                                for r in reversed(rows)
                            ]
                    except Exception:
                        continue

                return []

        except Exception as exc:
            logger.warning("Failed to fetch history for %s: %s", symbol, exc)
            return []

    # ── Data validation ───────────────────────────────────────────────────

    async def _fetch_intraday(self, symbol: str) -> list[dict[str, Any]]:
        """Fetch recent intraday trades for a symbol."""
        try:
            from sqlalchemy import select

            from core.database import async_session_factory

            async with async_session_factory() as session:
                try:
                    from models.market_data import IntradayTradeModel, SymbolModel

                    sym_result = await session.execute(select(SymbolModel.id).where(SymbolModel.symbol == symbol))
                    sym_id = sym_result.scalar()
                    if sym_id is None:
                        return []

                    query = (
                        select(
                            IntradayTradeModel.trade_date,
                            IntradayTradeModel.price,
                            IntradayTradeModel.volume,
                        )
                        .where(IntradayTradeModel.symbol_id == sym_id)
                        .limit(500)
                    )
                    result = await session.execute(query)
                    rows = result.fetchall()
                    return [{"date": str(r[0]), "price": r[1], "volume": r[2]} for r in rows]
                except Exception:
                    return []
        except Exception as exc:
            logger.debug("Intraday fetch skipped for %s: %s", symbol, exc)
            return []

    def _validate_data(
        self, symbol: str, bars: list[dict[str, Any]], intraday_bars: list[dict[str, Any]] | None = None
    ) -> bool:
        """Validate historical data quality. Returns True if data is usable for backtesting."""
        # Intraday check
        if intraday_bars is not None:
            if not intraday_bars:
                self.result.add_finding(
                    DiagnosticFinding(
                        level="WARNING",
                        category="data",
                        symbol=symbol,
                        message="No intraday trade data found",
                    )
                )
            else:
                self.result.add_finding(
                    DiagnosticFinding(
                        level="INFO",
                        category="data",
                        symbol=symbol,
                        message=f"Intraday data: {len(intraday_bars)} trades",
                    )
                )

        # Daily check
        if not bars:
            self.result.add_finding(
                DiagnosticFinding(
                    level="WARNING",
                    category="data",
                    symbol=symbol,
                    message="No historical data found",
                )
            )
            return False

        if len(bars) < MIN_BARS_FOR_BACKTEST:
            self.result.add_finding(
                DiagnosticFinding(
                    level="WARNING",
                    category="data",
                    symbol=symbol,
                    message=f"Insufficient bars: {len(bars)} (min: {MIN_BARS_FOR_BACKTEST})",
                )
            )
            return False

        issues: list[str] = []

        # Check for NaN / None / zero values
        nan_close = sum(
            1
            for b in bars
            if b.get("close", 0) == 0 or (isinstance(b.get("close"), float) and b["close"] != b["close"])
        )
        zero_vol = sum(1 for b in bars if b.get("volume", 0) == 0)
        bad_rows = sum(1 for b in bars if b["open"] == 0 and b["high"] == 0 and b["low"] == 0 and b["close"] == 0)

        if nan_close > 0:
            issues.append(f"{nan_close} bars with NaN/zero close")
        if zero_vol > len(bars) * 0.3:
            issues.append(f"{zero_vol}/{len(bars)} bars with zero volume")
        if bad_rows > len(bars) * 0.1:
            issues.append(f"{bad_rows} completely empty bars")

        # Check for date gaps (>5 trading days)
        gap_count = 0
        for i in range(1, len(bars)):
            d1_str = bars[i - 1].get("date", "")
            d2_str = bars[i].get("date", "")
            try:
                d1 = date.fromisoformat(d1_str[:10])
                d2 = date.fromisoformat(d2_str[:10])
                if (d2 - d1).days > 7:
                    gap_count += 1
            except (ValueError, TypeError):
                pass
        if gap_count > 0:
            issues.append(f"{gap_count} date gaps > 7 days")

        if issues:
            self.result.add_finding(
                DiagnosticFinding(
                    level="WARNING",
                    category="data",
                    symbol=symbol,
                    message=f"Data quality issues: {'; '.join(issues)}",
                    details=f"Total bars: {len(bars)}, first: {bars[0].get('date', '?')}, last: {bars[-1].get('date', '?')}",
                )
            )
            # Still return True — data may be usable despite warnings
        else:
            self.result.add_finding(
                DiagnosticFinding(
                    level="INFO",
                    category="data",
                    symbol=symbol,
                    message=f"Data OK: {len(bars)} bars",
                )
            )

        return True

    # ── Strategy registry helper ──────────────────────────────────────────

    def _get_registry(self):
        """Load and return the strategy registry (cached across calls)."""
        if self._registry_loaded:
            from backtesting.strategies.registry import get_strategy_registry

            return get_strategy_registry()

        try:
            from backtesting.strategies.registry import get_strategy_registry, register_all_strategies

            register_all_strategies()
            self._registry_loaded = True
            self._strategy_names = get_strategy_registry().list_names()
            logger.info("Loaded %d strategies from registry", len(self._strategy_names))
            return get_strategy_registry()
        except Exception as exc:
            logger.warning("Failed to load strategy registry: %s", exc)
            return None

    # ── Backtest smoke tests ──────────────────────────────────────────────

    async def _run_smoke_tests(self, symbol: str, bars: list[dict[str, Any]]) -> None:
        """Run a representative subset of strategies on the symbol."""
        try:
            registry = self._get_registry()
            if not registry:
                return

            # Prepare data slice for smoke testing
            test_bars = bars[-SMOKE_TEST_BARS:] if len(bars) > SMOKE_TEST_BARS else bars

            # Convert to backtest-compatible format
            data = []
            for b in test_bars:
                data.append(
                    {
                        "timestamp": b.get("date", ""),
                        "open": b["open"],
                        "high": b["high"],
                        "low": b["low"],
                        "close": b["close"],
                        "volume": b.get("volume", 0),
                        "prices": {symbol: b["close"]},
                    }
                )

            # Use all registered strategy names (or fallback if registry loaded partially)
            strat_names = self._strategy_names or [s["name"] for s in SMOKE_TEST_STRATEGIES]

            for strat_name in strat_names:
                strat_cls = registry.get(strat_name)
                if strat_cls is None:
                    continue

                t0 = time.perf_counter()
                try:
                    # Try to instantiate with appropriate parameters
                    try:
                        strategy = strat_cls()
                    except TypeError:
                        # Strategy requires params — inspect signature for smart defaults
                        import inspect

                        sig = inspect.signature(strat_cls.__init__)
                        strat_params: dict[str, Any] = {}
                        if "instrument_ids" in sig.parameters:
                            strat_params["instrument_ids"] = [symbol]
                        elif "instrument_id" in sig.parameters:
                            strat_params["instrument_id"] = symbol
                        if "sizing_method" in sig.parameters:
                            strat_params["sizing_method"] = "fixed"
                        if "sizing_value" in sig.parameters:
                            strat_params["sizing_value"] = 1000.0
                        strategy = strat_cls(**strat_params)

                    # Run smoke test
                    from backtesting.engine.backtest_engine import BacktestEngine

                    engine = BacktestEngine(initial_capital=SMOKE_TEST_CAPITAL)
                    result = await engine.run(strategy, data)

                    elapsed_ms = (time.perf_counter() - t0) * 1000

                    if result.total_trades == 0:
                        self.result.add_finding(
                            DiagnosticFinding(
                                level="INFO",
                                category="backtest",
                                symbol=symbol,
                                strategy=strat_name,
                                message=f"Strategy {strat_name}: 0 trades (no signals generated)",
                                duration_ms=elapsed_ms,
                            )
                        )
                    else:
                        self.result.add_finding(
                            DiagnosticFinding(
                                level="INFO",
                                category="backtest",
                                symbol=symbol,
                                strategy=strat_name,
                                message=(
                                    f"Strategy {strat_name}: "
                                    f"{result.total_trades} trades, "
                                    f"return={result.total_return_pct:.1f}%"
                                ),
                                duration_ms=elapsed_ms,
                            )
                        )

                except Exception as exc:
                    elapsed_ms = (time.perf_counter() - t0) * 1000
                    self.result.add_finding(
                        DiagnosticFinding(
                            level="ERROR",
                            category="backtest",
                            symbol=symbol,
                            strategy=strat_name,
                            message=f"Strategy {strat_name} crashed: {exc}",
                            details=traceback.format_exc(),
                            duration_ms=elapsed_ms,
                        )
                    )

        except ImportError as exc:
            self.result.add_finding(
                DiagnosticFinding(
                    level="WARNING",
                    category="system",
                    symbol="__ALL__",
                    message=f"Backtest smoke tests skipped — import error: {exc}",
                    details="Ensure backtesting modules are installed and importable.",
                )
            )
        except Exception as exc:
            self.result.add_finding(
                DiagnosticFinding(
                    level="ERROR",
                    category="system",
                    symbol="__ALL__",
                    message=f"Backtest smoke tests failed: {exc}",
                    details=traceback.format_exc(),
                )
            )

    # ── ML model check ────────────────────────────────────────────────────

    async def _check_ml_model(self, symbol: str) -> None:
        """Check if ML models are trained and can generate predictions."""
        try:
            from sqlalchemy import select

            from core.database import async_session_factory

            async with async_session_factory() as session:
                # Check ml_models table
                try:
                    from models.ml import MlModelModel

                    # NOTE: MlModelModel has no `status` column — it carries
                    # task/framework/latest_version. Report the total count.
                    result = await session.execute(select(MlModelModel.name))
                    models = result.fetchall()
                    if not models:
                        self.result.add_finding(
                            DiagnosticFinding(
                                level="INFO",
                                category="ml",
                                symbol="__ALL__",
                                message="No ML models found in registry",
                            )
                        )
                    else:
                        self.result.add_finding(
                            DiagnosticFinding(
                                level="INFO",
                                category="ml",
                                symbol="__ALL__",
                                message=f"ML models: {len(models)} registered",
                            )
                        )
                except Exception:
                    pass

                # Check ml_predictions for this symbol
                try:
                    from models.ml import MlPredictionModel

                    result = await session.execute(
                        select(MlPredictionModel.id).where(MlPredictionModel.symbol == symbol).limit(1)
                    )
                    if result.scalar() is None:
                        self.result.add_finding(
                            DiagnosticFinding(
                                level="WARNING",
                                category="ml",
                                symbol=symbol,
                                message="No ML predictions found for symbol",
                            )
                        )
                except Exception:
                    pass

                # Check ml_training_runs
                try:
                    from sqlalchemy import func

                    from models.ml import MlTrainingRunModel

                    result = await session.execute(select(func.count()).select_from(MlTrainingRunModel))
                    count = result.scalar() or 0
                    if count > 0:
                        self.result.add_finding(
                            DiagnosticFinding(
                                level="INFO",
                                category="ml",
                                symbol="__ALL__",
                                message=f"ML training runs found: {count}",
                            )
                        )
                except Exception:
                    pass

        except Exception as exc:
            self.result.add_finding(
                DiagnosticFinding(
                    level="WARNING",
                    category="ml",
                    symbol=symbol,
                    message=f"ML check failed: {exc}",
                )
            )

    # ── Cross-cutting checks ──────────────────────────────────────────────

    async def _cross_checks(self) -> None:
        """Run checks that span the entire system."""
        try:
            from sqlalchemy import text

            from core.database import async_session_factory

            async with async_session_factory() as session:
                # Check signal_accuracy table
                try:
                    result = await session.execute(text("SELECT COUNT(*) FROM signal_accuracy"))
                    count = result.scalar() or 0
                    if count > 0:
                        self.result.add_finding(
                            DiagnosticFinding(
                                level="INFO",
                                category="data",
                                symbol="__ALL__",
                                message=f"Signal accuracy records: {count}",
                            )
                        )
                except Exception:
                    self.result.add_finding(
                        DiagnosticFinding(
                            level="WARNING",
                            category="data",
                            symbol="__ALL__",
                            message="signal_accuracy table missing or empty",
                        )
                    )

                # Check alerts table
                try:
                    result = await session.execute(text("SELECT COUNT(*) FROM alerts"))
                    count = result.scalar() or 0
                    self.result.add_finding(
                        DiagnosticFinding(
                            level="INFO",
                            category="system",
                            symbol="__ALL__",
                            message=f"Active alerts: {count}",
                        )
                    )
                except Exception:
                    pass

                # Check backtest_runs
                try:
                    result = await session.execute(text("SELECT COUNT(*) FROM backtest_runs"))
                    count = result.scalar() or 0
                    self.result.add_finding(
                        DiagnosticFinding(
                            level="INFO",
                            category="backtest",
                            symbol="__ALL__",
                            message=f"Total backtest runs: {count}",
                        )
                    )
                except Exception:
                    pass

        except Exception as exc:
            logger.warning("Cross-checks failed: %s", exc)

    # ── Persistence ───────────────────────────────────────────────────────

    async def _persist_results(self) -> None:
        """Store diagnostic results in the database."""
        try:
            from sqlalchemy import text

            from core.database import async_session_factory

            async with async_session_factory() as session:
                # Create diagnostic tables if they don't exist
                await session.execute(
                    text("""
                    CREATE TABLE IF NOT EXISTS diagnostic_runs (
                        run_id VARCHAR(50) PRIMARY KEY,
                        started_at TIMESTAMP,
                        finished_at TIMESTAMP,
                        duration_seconds DOUBLE PRECISION,
                        total_symbols INTEGER,
                        total_findings INTEGER,
                        critical_count INTEGER DEFAULT 0,
                        error_count INTEGER DEFAULT 0,
                        warning_count INTEGER DEFAULT 0,
                        info_count INTEGER DEFAULT 0,
                        health_status VARCHAR(20),
                        summary JSONB
                    )
                """)
                )
                await session.execute(
                    text("""
                    CREATE TABLE IF NOT EXISTS diagnostic_findings (
                        id SERIAL PRIMARY KEY,
                        run_id VARCHAR(50) REFERENCES diagnostic_runs(run_id),
                        level VARCHAR(20),
                        category VARCHAR(50),
                        symbol VARCHAR(50),
                        message TEXT,
                        details TEXT,
                        strategy VARCHAR(50),
                        duration_ms DOUBLE PRECISION,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                )
                await session.commit()

                # Create indexes if needed
                await session.execute(
                    text("""
                    CREATE INDEX IF NOT EXISTS idx_diag_findings_run
                    ON diagnostic_findings(run_id)
                """)
                )
                await session.execute(
                    text("""
                    CREATE INDEX IF NOT EXISTS idx_diag_findings_level
                    ON diagnostic_findings(level)
                """)
                )
                await session.commit()

                # Insert run summary
                summary = self.result.summary()
                await session.execute(
                    text("""
                        INSERT INTO diagnostic_runs
                            (run_id, started_at, finished_at, duration_seconds,
                             total_symbols, total_findings,
                             critical_count, error_count, warning_count, info_count,
                             health_status, summary)
                        VALUES
                            (:run_id, :started_at, :finished_at, :duration_seconds,
                             :total_symbols, :total_findings,
                             :critical_count, :error_count, :warning_count, :info_count,
                             :health_status, :summary::jsonb)
                        ON CONFLICT (run_id) DO UPDATE SET
                            finished_at = EXCLUDED.finished_at,
                            total_findings = EXCLUDED.total_findings,
                            critical_count = EXCLUDED.critical_count,
                            error_count = EXCLUDED.error_count,
                            warning_count = EXCLUDED.warning_count,
                            info_count = EXCLUDED.info_count,
                            health_status = EXCLUDED.health_status,
                            summary = EXCLUDED.summary
                    """),
                    {
                        "run_id": self.result.run_id,
                        "started_at": self.result.started_at,
                        "finished_at": self.result.finished_at,
                        "duration_seconds": summary["duration_seconds"],
                        "total_symbols": self.result.total_symbols,
                        "total_findings": self.result.total_findings,
                        "critical_count": self.result.critical_count,
                        "error_count": self.result.error_count,
                        "warning_count": self.result.warning_count,
                        "info_count": self.result.info_count,
                        "health_status": summary["health"],
                    },
                )

                # Insert individual findings
                for f in self.result.findings:
                    await session.execute(
                        text("""
                            INSERT INTO diagnostic_findings
                                (run_id, level, category, symbol, message, details, strategy, duration_ms)
                            VALUES
                                (:run_id, :level, :category, :symbol, :message, :details, :strategy, :duration_ms)
                        """),
                        {
                            "run_id": self.result.run_id,
                            "level": f.level,
                            "category": f.category,
                            "symbol": f.symbol,
                            "message": f.message,
                            "details": f.details or "",
                            "strategy": f.strategy or "",
                            "duration_ms": f.duration_ms,
                        },
                    )

                await session.commit()
                logger.info("Persisted %d findings for run %s", self.result.total_findings, self.result.run_id)

        except Exception as exc:
            logger.error("Failed to persist diagnostic results: %s", exc)
            self.result.add_finding(
                DiagnosticFinding(
                    level="ERROR",
                    category="system",
                    symbol="__ALL__",
                    message=f"Failed to persist results to database: {exc}",
                )
            )


# ── CLI Entry Point ──────────────────────────────────────────────────────────


async def main() -> None:
    """CLI entry point for the diagnostic runner."""
    import argparse

    parser = argparse.ArgumentParser(description="Comprehensive system diagnostics for the trading platform")
    parser.add_argument(
        "--symbols",
        type=str,
        default="",
        help="Comma-separated list of symbols to check (default: all active)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_SYMBOL_LIMIT,
        help=f"Max symbols to check (default: {DEFAULT_SYMBOL_LIMIT})",
    )
    parser.add_argument(
        "--skip-backtests",
        action="store_true",
        help="Skip backtest smoke tests (data + ML checks only)",
    )
    parser.add_argument(
        "--skip-ml",
        action="store_true",
        help="Skip ML model checks",
    )
    parser.add_argument(
        "--output",
        type=str,
        choices=["json", "text"],
        default="text",
        help="Output format (default: text)",
    )
    args = parser.parse_args()

    # Initialize database
    try:
        from core.database import init_database

        await init_database()
    except Exception as exc:
        logger.error("Failed to initialize database: %s", exc)
        print(f"FATAL: Database initialization failed: {exc}")
        print("Ensure PostgreSQL is running and DATABASE_URL is set in .env")
        sys.exit(1)

    # Parse symbol filter
    symbol_filter = None
    if args.symbols:
        symbol_filter = [s.strip() for s in args.symbols.split(",") if s.strip()]

    # Run diagnostics
    runner = DiagnosticsRunner()
    result = await runner.run(
        symbol_filter=symbol_filter,
        limit=args.limit,
        skip_backtests=args.skip_backtests,
        skip_ml=args.skip_ml,
    )

    # Display results
    summary = result.summary()
    if args.output == "json":
        import json

        output = {
            **summary,
            "findings": [f.to_dict() for f in result.findings],
        }
        print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    else:
        print("\n" + "=" * 70)
        print("  DIAGNOSTIC REPORT")
        print("=" * 70)
        print(f"  Run ID:     {summary['run_id']}")
        print(
            f"  Duration:   {summary['duration_seconds']:.1f}s" if summary["duration_seconds"] else "  Duration:   N/A"
        )
        print(f"  Symbols:    {summary['total_symbols']}")
        print(f"  Findings:   {summary['total_findings']}")
        print(f"    Critical: {summary['by_level']['critical']}")
        print(f"    Errors:   {summary['by_level']['error']}")
        print(f"    Warnings: {summary['by_level']['warning']}")
        print(f"    Info:     {summary['by_level']['info']}")
        print(f"  Health:     {summary['health'].upper()}")
        print("=" * 70)

        if result.critical_count > 0 or result.error_count > 0:
            print("\n  !! ISSUES FOUND !!\n")
            for f in result.findings:
                if f.level in ("CRITICAL", "ERROR"):
                    tag = "🔴" if f.level == "CRITICAL" else "🟠"
                    print(f"  {tag} [{f.category}] {f.symbol}: {f.message}")
                    if f.strategy:
                        print(f"      Strategy: {f.strategy}")
            print()

        if result.warning_count > 0:
            print(f"  ⚠️  {result.warning_count} warnings (use --output json for full list)\n")

        if result.critical_count == 0 and result.error_count == 0:
            print("  ✅ All checks passed!\n")


if __name__ == "__main__":
    asyncio.run(main())
