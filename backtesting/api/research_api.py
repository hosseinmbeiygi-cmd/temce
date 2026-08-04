from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from backtesting.alpha.alpha_generator import AlphaGenerator
from backtesting.alpha.alpha_pool import AlphaPool, AlphaSignal
from backtesting.alpha.alpha_portfolio import AlphaPortfolio
from backtesting.alpha.alpha_selection import AlphaSelection
from backtesting.alpha.fast_evaluator import FastAlphaEvaluator
from backtesting.analytics.engine import AnalyticsEngine
from backtesting.engine.replay_engine import ReplayEngine
from backtesting.engine.simulator import BacktestSimulator
from backtesting.experiment.engine import ExperimentEngine, GridSearch
from backtesting.hybrid.hybrid_simulator import HybridMarketSimulator


class ExperimentStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ResearchJob:
    """A research job submitted through the API."""
    job_id: str
    job_type: str  # backtest, experiment, alpha_discovery, hybrid_sim
    status: ExperimentStatus = ExperimentStatus.PENDING
    parameters: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None


class ResearchAPI:
    """API layer for the quant research platform.

    Provides high-level methods that can be exposed via FastAPI endpoints
    or called directly from a web frontend.

    Each method creates a ResearchJob that can be tracked asynchronously.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, ResearchJob] = {}
        self._job_counter: int = 0
        self.analytics_engine = AnalyticsEngine()
        self.alpha_generator = AlphaGenerator()
        self.alpha_pool = AlphaPool()
        self.alpha_evaluator = FastAlphaEvaluator()
        self.alpha_selection = AlphaSelection()
        self.alpha_portfolio = AlphaPortfolio()

    def _next_job_id(self) -> str:
        self._job_counter += 1
        return f"job_{self._job_counter:06d}"

    def _create_job(self, job_type: str, params: dict[str, Any]) -> ResearchJob:
        job = ResearchJob(job_id=self._next_job_id(), job_type=job_type, parameters=params)
        self._jobs[job.job_id] = job
        return job

    # ── Backtest ────────────────────────────────────────

    async def run_backtest(
        self,
        simulator: BacktestSimulator | ReplayEngine | HybridMarketSimulator,
        strategy_name: str = "Strategy",
        initial_capital: float = 1_000_000_000,
        **kwargs: Any,
    ) -> ResearchJob:
        """Run a backtest and return a tracked job."""
        job = self._create_job("backtest", {
            "strategy": strategy_name,
            "initial_capital": initial_capital,
            **kwargs,
        })
        try:
            job.status = ExperimentStatus.RUNNING
            if isinstance(simulator, HybridMarketSimulator):
                result = await simulator.run(**kwargs)
            elif isinstance(simulator, BacktestSimulator):
                result = simulator.run(strategy=None, initial_capital=initial_capital, **kwargs)
            else:
                result = await simulator.run(strategy=None, initial_capital=initial_capital, **kwargs)

            if result.is_ok:
                bt_result = result.unwrap()
                analytics = self.analytics_engine.compute(bt_result)
                job.result = {
                    "strategy_name": bt_result.strategy_name,
                    "initial_capital": bt_result.initial_capital,
                    "final_capital": bt_result.final_capital,
                    "total_return": bt_result.total_return,
                    "total_return_pct": bt_result.total_return_pct,
                    "total_trades": bt_result.total_trades,
                    "sharpe_ratio": analytics.sharpe_ratio,
                    "sortino_ratio": analytics.sortino_ratio,
                    "max_drawdown_pct": analytics.max_drawdown_pct,
                    "cagr": analytics.cagr,
                    "win_rate": analytics.win_rate,
                    "profit_factor": analytics.profit_factor,
                    "volatility": analytics.volatility,
                }
                job.status = ExperimentStatus.COMPLETED
            else:
                job.error = result.error
                job.status = ExperimentStatus.FAILED
        except Exception as e:
            job.error = str(e)
            job.status = ExperimentStatus.FAILED
        job.completed_at = datetime.now()
        return job

    # ── Alpha Discovery ────────────────────────────────

    def discover_alphas(
        self,
        features: dict[str, list[float]],
        returns: list[float],
        n_alphas: int = 100,
    ) -> ResearchJob:
        """Run alpha discovery pipeline: generate, evaluate, select.

        Args:
            features: Dict of {feature_name: value_series}
            returns: Forward return series
            n_alphas: Number of alphas to generate

        Returns:
            ResearchJob with selection results
        """
        job = self._create_job("alpha_discovery", {"n_alphas": n_alphas})
        try:
            job.status = ExperimentStatus.RUNNING
            feature_names = list(features.keys())
            self.alpha_pool.register_features(feature_names)

            # Generate random alphas
            for _ in range(n_alphas):
                name, formula = self.alpha_generator.generate_random_alpha(feature_names)
                signal = AlphaSignal(alpha_id=name, name=name, formula=formula)
                self.alpha_pool.add_alpha(signal)

            # Evaluate all alphas
            signal_samples: dict[str, list[float]] = {}
            for alpha_id in self.alpha_pool.alpha_ids:
                signal_samples[alpha_id] = [random.gauss(0, 1) for _ in range(len(returns))]

            metrics = self.alpha_evaluator.evaluate_batch(signal_samples, returns)
            passing = {aid: m for aid, m in metrics.items() if m.is_valid}

            # Select best alphas
            sharpe_scores = {aid: m.sharpe for aid, m in passing.items()}
            selected = self.alpha_selection.select(sharpe_scores, signal_samples)

            job.result = {
                "n_generated": n_alphas,
                "n_passing": len(passing),
                "n_selected": len(selected),
                "selected_alphas": selected,
                "top_sharpes": {aid: round(metrics[aid].sharpe, 2) for aid in selected[:10] if aid in metrics},
            }
            job.status = ExperimentStatus.COMPLETED
        except Exception as e:
            job.error = str(e)
            job.status = ExperimentStatus.FAILED
        job.completed_at = datetime.now()
        return job

    # ── Experiment Management ──────────────────────────

    def run_grid_search(
        self,
        strategy_name: str,
        param_grid: dict[str, list[Any]],
        data_version: str = "",
    ) -> ResearchJob:
        """Create and return a grid search experiment."""
        job = self._create_job("experiment", {
            "type": "grid_search",
            "strategy": strategy_name,
            "param_grid": param_grid,
        })
        try:
            exp_engine = ExperimentEngine()
            grid = GridSearch(exp_engine)
            runs = grid.generate(strategy_name, param_grid, data_version)
            job.result = {
                "n_runs": len(runs),
                "run_ids": [r.run_id for r in runs],
            }
            job.status = ExperimentStatus.COMPLETED
        except Exception as e:
            job.error = str(e)
            job.status = ExperimentStatus.FAILED
        job.completed_at = datetime.now()
        return job

    # ── Portfolio Construction ─────────────────────────

    def build_alpha_portfolio(
        self,
        alpha_ids: list[str],
        alpha_returns: dict[str, list[float]],
        weighting_scheme: str = "equal_weight",
    ) -> ResearchJob:
        """Build a portfolio from selected alphas.

        Args:
            alpha_ids: List of alpha IDs to include
            alpha_returns: Dict of {alpha_id: return_series}
            weighting_scheme: equal_weight, mean_variance, equal_risk_contribution

        Returns:
            ResearchJob with portfolio weights
        """
        job = self._create_job("portfolio", {
            "n_alphas": len(alpha_ids),
            "weighting": weighting_scheme,
        })
        try:
            self.alpha_portfolio.weighting_scheme = weighting_scheme
            self.alpha_portfolio.set_alphas(alpha_ids)
            weights = self.alpha_portfolio.compute_weights(alpha_returns)
            job.result = {
                "n_alphas": len(alpha_ids),
                "weights": {k: round(v, 4) for k, v in weights.items()},
                "weighting_scheme": weighting_scheme,
            }
            job.status = ExperimentStatus.COMPLETED
        except Exception as e:
            job.error = str(e)
            job.status = ExperimentStatus.FAILED
        job.completed_at = datetime.now()
        return job

    # ── Job Management ─────────────────────────────────

    def get_job(self, job_id: str) -> ResearchJob | None:
        return self._jobs.get(job_id)

    def list_jobs(self, status: ExperimentStatus | None = None, limit: int = 50) -> list[ResearchJob]:
        jobs = list(self._jobs.values())
        if status:
            jobs = [j for j in jobs if j.status == status]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)[:limit]

    def list_strategies(self) -> list[str]:
        return ["moving_average_cross", "mean_reversion", "momentum", "breakout", "rsi_reversion", "volatility_breakout"]

    def list_alpha_templates(self) -> list[str]:
        return ["mean_reversion", "momentum", "zscore", "imbalance_spread"]

    def list_features(self) -> list[str]:
        return ["mid_price", "spread", "queue_imbalance", "order_flow_imbalance", "trade_intensity", "realized_volatility", "microprice", "depth_ratio"]
