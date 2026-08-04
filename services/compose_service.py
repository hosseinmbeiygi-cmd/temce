"""Compose Service: orchestrates strategy generation, filtering, and storage."""
from __future__ import annotations

from datetime import date
from typing import Any

from backtesting.composer.phase_runner import PhaseRunner
from backtesting.composer.pre_filter import PreTestFilter
from backtesting.composer.quality_filter import QualityFilter
from backtesting.composer.strategy_composer import StrategyComposer
from core.ids import new_id
from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class ComposeService:
    """Orchestrates the full strategy composition pipeline."""

    def __init__(self) -> None:
        self.composer = StrategyComposer(include_filters=True)
        self.pre_filter = PreTestFilter()
        self.quality_filter = QualityFilter()
        self.runner = PhaseRunner(self.pre_filter, self.quality_filter)
        self._running = False
        self._results: list[dict[str, Any]] = []
        self._stats: dict[str, Any] = {}

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def progress(self) -> dict[str, Any]:
        return {
            "running": self._running,
            **self.runner.progress,
            "pre_filter_stats": self.pre_filter.get_stats(),
            "quality_filter_stats": self.quality_filter.get_stats(),
            "total_results": len(self._results),
        }

    async def start(
        self,
        symbols: list[str],
        start_date: date | None = None,
        end_date: date | None = None,
        capital: float = 1_000_000_000,
        batch_size: int = 100_000,
        max_batches: int = 10,
    ) -> Result[dict[str, Any]]:
        """Start generating strategies in batches."""
        if self._running:
            return Result.fail("Generation already in progress")

        self._running = True
        self._results = []
        self.pre_filter.reset_stats()
        self.quality_filter.reset_stats()

        try:
            today = date.today()
            start = start_date or date(today.year - 2, 1, 1)
            end = end_date or today

            # Load data for symbols
            from services.backtest_service import BacktestService
            svc = BacktestService()
            symbol_data: dict[str, list[dict]] = {}
            for sym in symbols:
                data = await svc._load_historical_data(sym, start, end)
                if data:
                    symbol_data[sym] = data

            if not symbol_data:
                self._running = False
                return Result.fail("No data found for any symbol")

            # Estimate total combinations
            total_estimated = self.composer.estimate_total_count()
            logger.info("Estimated total combinations: %d", total_estimated)

            # Process in batches
            batch_id = new_id("batch")
            offset = 0
            all_results: list[dict[str, Any]] = []

            for batch_num in range(max_batches):
                if not self._running:
                    break

                logger.info("Processing batch %d (offset=%d, size=%d)", batch_num + 1, offset, batch_size)

                # Generate blueprints for this batch
                blueprints = self.composer.generate_batch(offset, batch_size)
                if not blueprints:
                    break

                # Run batch against each symbol
                for sym, data in symbol_data.items():
                    if not self._running:
                        break

                    batch_results = await self.runner.run_batch(
                        blueprints=blueprints,
                        data=data,
                        capital=capital,
                        symbol=sym,
                        max_workers=4,
                    )

                    for r in batch_results:
                        r["batch_id"] = batch_id
                        r["symbol"] = sym

                    all_results.extend(batch_results)

                offset += batch_size

            # Sort by score and keep top results
            all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
            self._results = all_results[:500]  # Keep top 500

            # Save to DB
            try:
                from core.database import async_session_factory
                from repositories.generated_strategy_repository import GeneratedStrategyRepository
                if async_session_factory:
                    async with async_session_factory() as session:
                        repo = GeneratedStrategyRepository(session)
                        save_count = 0
                        for r in self._results:
                            bp = r.get("blueprint", {})
                            entry = bp.get("entry", {})
                            exit_ = bp.get("exit", {})
                            f1 = bp.get("filter1")
                            m = r.get("metrics", {})
                            save_data = {
                                "id": new_id("gs"),
                                "symbol": r.get("symbol", ""),
                                "entry_indicator": entry.get("indicator"),
                                "entry_params": entry.get("params"),
                                "entry_condition": entry.get("condition"),
                                "exit_indicator": exit_.get("indicator"),
                                "exit_params": exit_.get("params"),
                                "exit_condition": exit_.get("condition"),
                                "filter1_indicator": f1.get("indicator") if f1 else None,
                                "filter1_params": f1.get("params") if f1 else None,
                                "filter1_condition": f1.get("condition") if f1 else None,
                                "stop_loss_pct": bp.get("stop_loss_pct"),
                                "take_profit_pct": bp.get("take_profit_pct"),
                                "sizing_method": bp.get("sizing_method"),
                                "sizing_value": bp.get("sizing_value"),
                                "total_return_pct": m.get("total_return_pct"),
                                "annualized_return_pct": m.get("annualized_return_pct"),
                                "sharpe_ratio": m.get("sharpe_ratio"),
                                "sortino_ratio": m.get("sortino_ratio"),
                                "calmar_ratio": m.get("calmar_ratio"),
                                "max_drawdown_pct": m.get("max_drawdown_pct"),
                                "win_rate": m.get("win_rate"),
                                "profit_factor": m.get("profit_factor"),
                                "total_trades": m.get("total_trades"),
                                "winning_trades": m.get("winning_trades"),
                                "losing_trades": m.get("losing_trades"),
                                "score": r.get("score", 0),
                                "strategy_type": r.get("strategy_type"),
                                "batch_id": batch_id,
                            }
                            await repo.save(save_data)
                            save_count += 1
                        await session.commit()
                        logger.info("Saved %d strategies to DB", save_count)
            except Exception as db_err:
                logger.warning("Failed to save to DB: %s", db_err)

            self._stats = {
                "batch_id": batch_id,
                "symbols": symbols,
                "total_tested": self.pre_filter.stats.get("total", 0) + len(all_results),
                "pre_filtered": self.pre_filter.stats.get("total", 0) - self.pre_filter.stats.get("passed", 0),
                "passed_quality": len(all_results),
                "top_results": len(self._results),
                "pre_filter_stats": self.pre_filter.get_stats(),
                "quality_filter_stats": self.quality_filter.get_stats(),
            }

            self._running = False
            return Result.ok(self._stats)

        except Exception as e:
            self._running = False
            logger.exception("Composition failed")
            return Result.fail(str(e))

    def stop(self) -> None:
        self._running = False
        self.runner.cancel()

    def get_results(
        self,
        symbol: str | None = None,
        entry_indicator: str | None = None,
        exit_indicator: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get filtered results."""
        results = self._results

        if symbol:
            results = [r for r in results if r.get("symbol") == symbol]
        if entry_indicator:
            results = [r for r in results if r.get("blueprint", {}).get("entry", {}).get("indicator") == entry_indicator]
        if exit_indicator:
            results = [r for r in results if r.get("blueprint", {}).get("exit", {}).get("indicator") == exit_indicator]

        return results[:limit]

    def get_top(self, n: int = 10) -> list[dict[str, Any]]:
        return self._results[:n]

    def get_indicator_stats(self) -> list[dict[str, Any]]:
        """Get stats per indicator from results."""
        stats: dict[str, dict] = {}
        for r in self._results:
            entry = r.get("blueprint", {}).get("entry", {}).get("indicator", "unknown")
            if entry not in stats:
                stats[entry] = {"count": 0, "total_score": 0, "total_return": 0}
            stats[entry]["count"] += 1
            stats[entry]["total_score"] += r.get("score", 0)
            stats[entry]["total_return"] += r.get("metrics", {}).get("total_return_pct", 0)

        return [
            {"indicator": k, "count": v["count"],
             "avg_score": round(v["total_score"] / v["count"], 2) if v["count"] > 0 else 0,
             "avg_return": round(v["total_return"] / v["count"], 2) if v["count"] > 0 else 0}
            for k, v in sorted(stats.items(), key=lambda x: x[1]["count"], reverse=True)
        ]

    def export_csv(self) -> str:
        """Export results as CSV."""
        if not self._results:
            return ""
        headers = ["symbol", "entry", "exit", "filter", "return%", "sharpe", "dd%", "win_rate", "pf", "trades", "score"]
        lines = ["|".join(headers)]
        for r in self._results:
            m = r.get("metrics", {})
            bp = r.get("blueprint", {})
            entry = bp.get("entry", {}).get("indicator", "")
            exit_ = bp.get("exit", {}).get("indicator", "")
            f1 = bp.get("filter1", {}).get("indicator", "") if bp.get("filter1") else ""
            lines.append("|".join([
                r.get("symbol", ""),
                entry, exit_, f1,
                str(m.get("total_return_pct", 0)),
                str(m.get("sharpe_ratio", 0)),
                str(m.get("max_drawdown_pct", 0)),
                str(m.get("win_rate", 0)),
                str(m.get("profit_factor", 0)),
                str(m.get("total_trades", 0)),
                str(r.get("score", 0)),
            ]))
        return "\n".join(lines)


# Singleton
_compose_service: ComposeService | None = None


def get_compose_service() -> ComposeService:
    global _compose_service
    if _compose_service is None:
        _compose_service = ComposeService()
    return _compose_service
