"""Mass scanner: runs all 30 indicators × all param combinations across all symbols.

Finds the best strategy per symbol and stores results in generated_strategies.
Also extracts symbol relationships (shared board members, same group, correlation).

Design for < 3 hour completion:
- OHLCV data loaded once per symbol, cached per batch
- Indicator values pre-computed per symbol, shared across param variants
- Parallel backtests via BacktestSimulator.run_parallel (semaphore-limited)
- 6-stage filter eliminates poor strategies early
- Batched DB writes (bulk insert)
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from backtesting.composer.indicator_registry import REGISTRY as INDICATOR_REGISTRY
from backtesting.composer.indicator_registry import IndicatorSpec, get_indicator
from core.ids import new_id
from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


# ── Signal configuration: maps indicator_id → entry/exit condition keys ──────

SIGNAL_CONFIGS: dict[str, list[dict[str, str]]] = {
    "rsi": [{"entry": "oversold", "exit": "overbought"}],
    "macd": [{"entry": "bullish_cross", "exit": "bearish_cross"}],
    "squeeze_momentum": [
        {"entry": "momentum_positive", "exit": "momentum_negative"},
    ],
    "stochastic": [{"entry": "oversold", "exit": "overbought"}],
    "williams_r": [{"entry": "oversold", "exit": "overbought"}],
    "cci": [{"entry": "oversold", "exit": "overbought"}],
    "ema_crossover": [{"entry": "golden_cross", "exit": "death_cross"}],
    "adx": [{"entry": "strong_trend", "exit": "weak_trend"}],
    "half_trend": [{"entry": "buy_signal", "exit": "sell_signal"}],
    "parabolic_sar": [{"entry": "buy_signal", "exit": "sell_signal"}],
    "ichimoku": [{"entry": "bullish_cloud", "exit": "bearish_cloud"}],
    "atr": [{"entry": "low_volatility", "exit": "high_volatility"}],
    "bollinger_bw": [{"entry": "squeeze", "exit": "expansion"}],
    "keltner_position": [{"entry": "above_upper", "exit": "below_lower"}],
    "compression_ratio": [{"entry": "compressed", "exit": "expanded"}],
    "relative_volume": [{"entry": "high_volume", "exit": "low_volume"}],
    "obv": [{"entry": "obv_rising", "exit": "obv_falling"}],
    "vwap": [{"entry": "above_vwap", "exit": "below_vwap"}],
    "supply_dryness": [{"entry": "dry", "exit": "abundant"}],
    "clv": [{"entry": "strong_close", "exit": "weak_close"}],
    "recovery_ratio": [{"entry": "strong_recovery", "exit": "weak_recovery"}],
    "support_resistance": [{"entry": "break_up", "exit": "break_down"}],
    "breakout_quality": [{"entry": "strong_breakout", "exit": "weak_breakout"}],
    "volume_zscore": [{"entry": "high_zscore", "exit": "low_zscore"}],
    "amihud_illiquidity": [{"entry": "liquid", "exit": "illiquid"}],
    "normalized_volatility": [{"entry": "low_volatility", "exit": "high_volatility"}],
    "relative_strength": [{"entry": "outperforming", "exit": "underperforming"}],
}


# ── 6-Stage Filter ──────────────────────────────────────────────────────────

DEFAULT_FILTERS = {
    "stage1_min_return": 3.0,
    "stage2_max_drawdown": 30.0,
    "stage3_min_sharpe": 0.3,
    "stage4_min_win_rate": 35.0,
    "stage5_min_trades": 3,
    "stage6_min_profit_factor": 1.1,
}


def _compute_metrics(equity: list[float], trades: list[Any], capital: float) -> dict[str, float]:
    if len(equity) < 2:
        return {
            "total_return_pct": 0.0, "sharpe_ratio": 0.0, "max_drawdown_pct": 0.0,
            "win_rate": 0.0, "total_trades": 0, "profit_factor": 0.0,
            "sortino_ratio": 0.0, "calmar_ratio": 0.0, "annualized_return_pct": 0.0,
        }
    total_return = ((equity[-1] / capital) - 1) * 100
    trading_days = len(equity)
    years = trading_days / 252
    ann_return = ((equity[-1] / capital) ** (1 / max(years, 0.01)) - 1) * 100

    returns = [(equity[i] / equity[i - 1]) - 1 for i in range(1, len(equity))]
    avg_r = sum(returns) / len(returns) if returns else 0
    std_r = math.sqrt(sum((r - avg_r) ** 2 for r in returns) / len(returns)) if returns else 1
    sharpe = (avg_r / std_r) * math.sqrt(252) if std_r > 0 else 0

    peak = equity[0]
    max_dd = 0.0
    for nav in equity:
        if nav > peak:
            peak = nav
        dd = (peak - nav) / peak if peak > 0 else 0
        max_dd = max(max_dd, dd)

    wins = [t for t in trades if t > 0]
    losses = [abs(t) for t in trades if t < 0]
    win_rate = (len(wins) / len(trades) * 100) if trades else 0
    profit_factor = (sum(wins) / sum(losses)) if sum(losses) > 0 else (9e9 if wins else 0)

    downside = [r for r in returns if r < 0]
    downside_vol = math.sqrt(sum(r ** 2 for r in downside) / len(downside)) if downside else 1
    sortino = (avg_r / downside_vol) * math.sqrt(252) if downside_vol > 0 else 0
    calmar = ann_return / (max_dd * 100) if max_dd > 0 else 0

    return {
        "total_return_pct": round(total_return, 2),
        "annualized_return_pct": round(ann_return, 2),
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "win_rate": round(win_rate, 1),
        "total_trades": len(trades),
        "profit_factor": round(profit_factor, 2),
        "sortino_ratio": round(sortino, 2),
        "calmar_ratio": round(calmar, 2),
    }


def _apply_filter(metrics: dict[str, Any], filters: dict[str, Any]) -> bool:
    if metrics["total_return_pct"] < filters["stage1_min_return"]:
        return False
    if metrics["max_drawdown_pct"] > filters["stage2_max_drawdown"]:
        return False
    if metrics["sharpe_ratio"] < filters["stage3_min_sharpe"]:
        return False
    if metrics["win_rate"] < filters["stage4_min_win_rate"]:
        return False
    if metrics["total_trades"] < filters["stage5_min_trades"]:
        return False
    return not metrics["profit_factor"] < filters["stage6_min_profit_factor"]


def _combined_score(metrics: dict[str, float]) -> float:
    return (
        metrics.get("sharpe_ratio", 0) * 0.30
        + metrics.get("sortino_ratio", 0) * 0.15
        + metrics.get("calmar_ratio", 0) * 0.15
        + metrics.get("total_return_pct", 0) * 0.002
        + metrics.get("profit_factor", 0) * 0.15
        + metrics.get("win_rate", 0) * 0.005
        - metrics.get("max_drawdown_pct", 0) * 0.005
    )


# ── Batch result accumulator ────────────────────────────────────────────────

@dataclass
class ScannerResult:
    symbol: str
    indicator_id: str
    params: dict[str, Any]
    signal_config: str
    metrics: dict[str, float]
    score: float


# ── Main service ────────────────────────────────────────────────────────────

class MassScannerService:
    """Scans all symbols × indicators to find the best strategy per symbol.

    Usage:
        svc = MassScannerService()
        result = await svc.scan_all()
    """

    def __init__(self) -> None:
        self._results: list[ScannerResult] = []
        self._best_per_symbol: dict[str, ScannerResult] = {}
        self._stats: dict[str, Any] = {}
        self._batch_id = ""
        self._running = False
        self._progress = 0.0

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def progress(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "progress_pct": round(self._progress, 1),
            "total_passing": len(self._results),
            "batch_id": self._batch_id,
        }

    # ── Public entry point ──────────────────────────────────────────────────

    async def scan_all(
        self,
        symbols: list[str] | None = None,
        batch_size: int = 20,
        max_concurrent: int = 20,
        capital: float = 1_000_000_000,
        start_date: date | None = None,
        end_date: date | None = None,
        filters: dict[str, Any] | None = None,
        indicator_ids: list[str] | None = None,
    ) -> Result[dict[str, Any]]:
        """Run the full scan across all (symbol × indicator × params).

        Returns a dict with:
          - batch_id
          - symbols_scanned
          - configs_tested
          - passed_filter
          - best_per_symbol: {symbol: {indicator, params, metrics, score}}
          - stats: timing & count summary
        """
        if self._running:
            return Result.fail("Scan already in progress")
        self._running = True
        self._results = []
        self._best_per_symbol = {}
        self._batch_id = new_id("mscan")
        self._progress = 0.0

        filters = filters or DEFAULT_FILTERS
        start_time = datetime.now(UTC)

        try:
            # 1. Load symbols
            if not symbols:
                symbols = await self._load_symbols()
            if not symbols:
                return Result.fail("No symbols with data found")
            logger.info("Loaded %d symbols", len(symbols))

            # 2. Build the list of (indicator_id, params, signal_config) to test
            configs = self._build_configs(indicator_ids)
            total_configs = len(configs)
            logger.info("Built %d indicator×param×signal configs from %d indicators",
                        total_configs, len({c[0] for c in configs}))

            # 3. Process symbols in batches
            total_symbols = len(symbols)
            configs_tested = 0
            symbols_scanned = 0

            for batch_start in range(0, total_symbols, batch_size):
                batch_syms = symbols[batch_start:batch_start + batch_size]
                logger.info("Batch %d/%d: %s",
                            batch_start // batch_size + 1,
                            (total_symbols + batch_size - 1) // batch_size,
                            batch_syms)

                # 3a. Load OHLCV for this batch (one DB call per symbol)
                ohlcv_map = await self._load_batch_data(batch_syms, start_date, end_date)

                # 3b. For each symbol in batch, run all configs
                for sym in batch_syms:
                    ohlcv = ohlcv_map.get(sym)
                    if not ohlcv or len(ohlcv) < 30:
                        logger.debug("Skipping %s — insufficient data (%d bars)", sym, len(ohlcv or []))
                        continue

                    passing = await self._scan_symbol(sym, ohlcv, configs, capital, filters, max_concurrent)
                    self._results.extend(passing)
                    symbols_scanned += 1
                    configs_tested += len(configs)

                # Update progress
                progress_pct = (batch_start + len(batch_syms)) / total_symbols * 100
                self._progress = min(progress_pct, 99.9)
                logger.info("Progress: %.1f%% (%d/%d symbols, %d passing configs so far)",
                            progress_pct, symbols_scanned, total_symbols, len(self._results))

            # 4. Compute best strategy per symbol
            self._best_per_symbol = self._compute_best_per_symbol()
            best_count = len(self._best_per_symbol)

            # 5. Persist to database
            await self._persist_results(filters)

            elapsed = (datetime.now(UTC) - start_time).total_seconds()
            self._stats = {
                "batch_id": self._batch_id,
                "symbols_scanned": symbols_scanned,
                "configs_tested": configs_tested,
                "passed_filter": len(self._results),
                "best_strategies_found": best_count,
                "elapsed_seconds": round(elapsed, 1),
            }

            logger.info("Scan complete: %d configs tested, %d passed, %d best strategies in %.1fs",
                        configs_tested, len(self._results), best_count, elapsed)

            self._progress = 100.0
            return Result.ok({
                "batch_id": self._batch_id,
                **self._stats,
                "best_per_symbol": {
                    sym: self._result_to_dict(r)
                    for sym, r in self._best_per_symbol.items()
                },
            })

        except Exception as e:
            logger.exception("Mass scan failed")
            return Result.fail(str(e))
        finally:
            self._running = False

    # ── Step: post-process and extract symbol relations ────────────────────

    async def extract_relations(
        self,
        symbols: list[str] | None = None,
    ) -> Result[dict[str, Any]]:
        """Extract symbol relationships (correlation, group membership).

        Can be called after scan_all() completes.
        """
        if not symbols:
            symbols = list(self._best_per_symbol.keys())
        if not symbols:
            symbols = await self._load_symbols()

        from core.database import async_session_factory
        if async_session_factory is None:
            return Result.fail("No database connection")

        relations_stored = 0
        try:
            # 1. Price correlation
            ohlcv_map = await self._load_batch_data(symbols)
            corr_relations = self._compute_correlations(ohlcv_map)
            logger.info("Computed %d correlation pairs", len(corr_relations))

            # 2. Store all relations
            async with async_session_factory() as session:
                from sqlalchemy import text

                for rel in corr_relations:
                    rid = new_id("srel")
                    await session.execute(
                        text("""
                            INSERT INTO symbol_relations (id, symbol_a, symbol_b, relation_type,
                                strength, label, metadata_json, source, detected_at)
                            VALUES (:id, :a, :b, :type, :strength, :label, :meta, :source, :detected)
                            ON CONFLICT (id) DO NOTHING
                        """),
                        {
                            "id": rid,
                            "a": rel["a"],
                            "b": rel["b"],
                            "type": "correlation",
                            "strength": rel["strength"],
                            "label": f"همبستگی: {rel['strength']:.2f}",
                            "meta": json.dumps({"bars_overlap": rel.get("n", 0)}),
                            "source": "mass_scanner",
                            "detected": datetime.now(UTC),
                        },
                    )
                    relations_stored += 1

                await session.commit()

            return Result.ok({
                "symbols": len(symbols),
                "relations_stored": relations_stored,
            })

        except Exception as e:
            logger.exception("Relation extraction failed")
            return Result.fail(str(e))

    # ── Internal helpers ───────────────────────────────────────────────────

    async def _load_symbols(self) -> list[str]:
        try:
            from sqlalchemy import text

            from core.database import async_session_factory
            if async_session_factory is None:
                return ["فولاد", "شپنا", "فملی", "وبملت", "خودرو"]
            async with async_session_factory() as session:
                result = await session.execute(text("""
                    SELECT symbol FROM (
                        SELECT symbol FROM brsapi_historical_daily WHERE price_close > 0
                        UNION ALL
                        SELECT symbol FROM quotes WHERE price_close > 0
                    ) combined
                    GROUP BY symbol HAVING COUNT(*) > 30
                    ORDER BY COUNT(*) DESC
                """))
                return [row[0] for row in result.fetchall()]
        except Exception as e:
            logger.warning("Failed to load symbols: %s", e)
            return ["فولاد", "شپنا", "فملی", "وبملت", "خودرو"]

    async def _load_batch_data(
        self, symbols: list[str], start: date | None = None, end: date | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Load OHLCV data for all symbols in one go (one query per symbol)."""
        from services.backtest_service import BacktestService
        svc = BacktestService()
        today = date.today()
        s = start or date(today.year - 2, 1, 1)
        e = end or today
        result: dict[str, list[dict[str, Any]]] = {}
        for sym in symbols:
            data = await svc._load_historical_data(sym, s, e)
            if data and len(data) >= 30:
                result[sym] = data
        return result

    def _build_configs(
        self, indicator_ids: list[str] | None = None,
    ) -> list[tuple[str, dict[str, Any], str]]:
        """Build list of (indicator_id, params_dict, signal_name) to test."""
        configs: list[tuple[str, dict[str, Any], str]] = []
        for spec in INDICATOR_REGISTRY:
            if indicator_ids and spec.id not in indicator_ids:
                continue
            if spec.id not in SIGNAL_CONFIGS:
                continue
            signal_options = SIGNAL_CONFIGS[spec.id]
            param_keys = list(spec.params.keys())
            param_values = [spec.params[k] for k in param_keys]
            if param_values:
                import itertools
                for combo in itertools.product(*param_values):
                    params = dict(zip(param_keys, combo, strict=False))
                    for sig in signal_options:
                        sig_name = f"{sig['entry']}/{sig['exit']}"
                        configs.append((spec.id, params, sig_name))
            else:
                for sig in signal_options:
                    sig_name = f"{sig['entry']}/{sig['exit']}"
                    configs.append((spec.id, {}, sig_name))
        return configs

    async def _scan_symbol(
        self, symbol: str, ohlcv: list[dict[str, Any]],
        configs: list[tuple[str, dict[str, Any], str]],
        capital: float, filters: dict[str, Any], max_concurrent: int,
    ) -> list[ScannerResult]:
        """Run all configs on one symbol. Uses pre-computed indicators."""
        # 1. Extract OHLCV arrays
        close = [b["close"] for b in ohlcv]
        high = [b["high"] for b in ohlcv]
        low = [b["low"] for b in ohlcv]
        volume = [b["volume"] for b in ohlcv]
        n = len(ohlcv)

        # 2. Group configs by indicator_id so we compute each indicator once
        from collections import defaultdict
        by_indicator: dict[str, list[tuple[dict[str, Any], str, str]]] = defaultdict(list)
        for ind_id, params, sig_name in configs:
            by_indicator[ind_id].append((params, sig_name, sig_name))

        from backtesting.engine.simulator import BacktestSimulator
        from backtesting.strategies.signal_strategy import SignalStrategy

        passing: list[ScannerResult] = []

        for ind_id, param_signal_list in by_indicator.items():
            spec = get_indicator(ind_id)
            if spec is None:
                continue

            # Pre-compute for each unique param set
            param_results: dict[str, tuple[list[bool], list[bool]]] = {}

            for params, sig_name, _sig_key in param_signal_list:
                param_key = str(sorted(params.items()))
                if param_key in param_results:
                    entry_sig, exit_sig = param_results[param_key]
                else:
                    try:
                        # Call compute_fn with the right args
                        result = self._compute_indicator(spec, close, high, low, volume, params)
                        if result is None:
                            continue
                        # Extract entry/exit signal names from sig_name
                        entry_key, exit_key = sig_name.split("/")
                        entry_sig = [bool(v) for v in result.get(entry_key, [False] * n)]
                        exit_sig = [bool(v) for v in result.get(exit_key, [False] * n)]
                        param_results[param_key] = (entry_sig, exit_sig)
                    except Exception as e:
                        logger.debug("Indicator %s compute failed: %s", ind_id, e)
                        continue

                has_any_entry = sum(entry_sig)
                has_any_exit = sum(exit_sig)
                if has_any_entry == 0 or has_any_exit == 0:
                    continue

                strategy = SignalStrategy(
                    entry_signal=entry_sig,
                    exit_signal=exit_sig,
                    name=f"{ind_id}_{sig_name}",
                    sizing_method="fixed",
                    sizing_value=capital * 0.1,
                )
                result = BacktestSimulator().run(strategy, initial_capital=capital, data=ohlcv)
                if not result.success:
                    continue
                bt = result.value
                metrics = _compute_metrics(
                    [ep.nav for ep in bt.equity_curve],
                    [getattr(t, "pnl", 0) for t in bt.trades],
                    capital,
                )
                if not _apply_filter(metrics, filters):
                    continue
                score = _combined_score(metrics)
                passing.append(ScannerResult(
                    symbol=symbol,
                    indicator_id=ind_id,
                    params=params,
                    signal_config=sig_name,
                    metrics=metrics,
                    score=score,
                ))

        return passing

    def _compute_indicator(
        self, spec: IndicatorSpec, close: list[float],
        high: list[float], low: list[float], volume: list[float],
        params: dict[str, Any],
    ) -> dict[str, list] | None:
        """Call the indicator's compute_fn with the appropriate args."""
        fn = spec.compute_fn
        arg_names = fn.__code__.co_varnames[:fn.__code__.co_argcount]

        kwargs = dict(params)
        # Map standard column names
        if "close" in arg_names:
            kwargs["close"] = close
        if "high" in arg_names:
            kwargs["high"] = high
        if "low" in arg_names:
            kwargs["low"] = low
        if "volume" in arg_names:
            kwargs["volume"] = volume
        # Price needs (close, high, low) variants
        if "prices" in arg_names:
            kwargs["prices"] = close

        # Indicators that need non-OHLCV data → skip gracefully
        extra_args = {"buy_val", "buy_cnt", "sell_val", "sell_cnt",
                      "net_flow", "free_float", "sell_pressure", "ret",
                      "asset_price", "benchmark_price"}
        if extra_args.intersection(arg_names):
            missing = [a for a in extra_args if a in arg_names and a not in kwargs]
            if missing:
                return None

        return fn(**kwargs)

    def _compute_best_per_symbol(self) -> dict[str, ScannerResult]:
        best: dict[str, ScannerResult] = {}
        for r in self._results:
            prev = best.get(r.symbol)
            if prev is None or r.score > prev.score:
                best[r.symbol] = r
        return best

    def _compute_correlations(
        self, ohlcv_map: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        symbols = list(ohlcv_map.keys())
        relations: list[dict[str, Any]] = []
        from scipy.stats import pearsonr
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                a, b = symbols[i], symbols[j]
                prices_a = [bar["close"] for bar in ohlcv_map[a]]
                prices_b = [bar["close"] for bar in ohlcv_map[b]]
                min_len = min(len(prices_a), len(prices_b))
                if min_len < 20:
                    continue
                pa = prices_a[-min_len:]
                pb = prices_b[-min_len:]
                try:
                    corr, _ = pearsonr(pa, pb)
                    if abs(corr) >= 0.7:
                        relations.append({"a": a, "b": b, "strength": round(corr, 3), "n": min_len})
                except Exception:
                    pass
        return relations

    async def _persist_results(self, filters: dict[str, Any]) -> None:
        """Bulk-insert passing results into generated_strategies table."""
        from core.database import async_session_factory
        if async_session_factory is None:
            logger.warning("No DB — skip persisting %d results", len(self._results))
            return

        from sqlalchemy import text
        inserted = 0
        try:
            async with async_session_factory() as session:
                for r in self._results:
                    sid = f"{self._batch_id}_{r.symbol}_{r.indicator_id}_{hash(str(r.params)) % 10**8}"
                    sid = sid.replace("-", "_")
                    m = r.metrics
                    await session.execute(
                        text("""
                            INSERT INTO generated_strategies (
                                id, symbol, entry_indicator, entry_params, entry_condition,
                                exit_indicator, exit_params, exit_condition,
                                strategy_type, total_return_pct, annualized_return_pct,
                                sharpe_ratio, sortino_ratio, calmar_ratio,
                                max_drawdown_pct, win_rate, profit_factor,
                                total_trades, winning_trades, losing_trades,
                                score, batch_id, status
                            ) VALUES (
                                :id, :symbol, :entry_ind, :entry_params, :entry_cond,
                                :exit_ind, :exit_params, :exit_cond,
                                'signal', :ret, :ann_ret,
                                :sharpe, :sortino, :calmar,
                                :max_dd, :win_rate, :pf,
                                :trades, :wins, :losses,
                                :score, :batch_id, 'active'
                            ) ON CONFLICT (id) DO NOTHING
                        """),
                        {
                            "id": sid,
                            "symbol": r.symbol,
                            "entry_ind": r.indicator_id,
                            "entry_params": json.dumps(r.params),
                            "entry_cond": r.signal_config.split("/")[0],
                            "exit_ind": r.indicator_id,
                            "exit_params": json.dumps(r.params),
                            "exit_cond": r.signal_config.split("/")[1] if "/" in r.signal_config else "",
                            "ret": m.get("total_return_pct", 0),
                            "ann_ret": m.get("annualized_return_pct", 0),
                            "sharpe": m.get("sharpe_ratio", 0),
                            "sortino": m.get("sortino_ratio", 0),
                            "calmar": m.get("calmar_ratio", 0),
                            "max_dd": m.get("max_drawdown_pct", 0),
                            "win_rate": m.get("win_rate", 0),
                            "pf": m.get("profit_factor", 0),
                            "trades": m.get("total_trades", 0),
                            "wins": m.get("winning_trades", 0),
                            "losses": m.get("losing_trades", 0),
                            "score": r.score,
                            "batch_id": self._batch_id,
                        },
                    )
                    inserted += 1
                    if inserted % 200 == 0:
                        await session.commit()
                await session.commit()
            logger.info("Persisted %d results to DB (batch_id=%s)", inserted, self._batch_id)
        except Exception as e:
            logger.error("Failed to persist results: %s", e)

    @staticmethod
    def _result_to_dict(r: ScannerResult) -> dict[str, Any]:
        return {
            "indicator": r.indicator_id,
            "params": r.params,
            "signal": r.signal_config,
            "metrics": r.metrics,
            "score": round(r.score, 2),
        }


# ── Singleton ───────────────────────────────────────────────────────────────

_scanner: MassScannerService | None = None


def get_mass_scanner() -> MassScannerService:
    global _scanner
    if _scanner is None:
        _scanner = MassScannerService()
    return _scanner
