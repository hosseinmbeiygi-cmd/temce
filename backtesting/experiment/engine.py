from __future__ import annotations

import itertools
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from backtesting.types import BacktestResult


class ExperimentStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExperimentRun:
    run_id: str
    strategy: str
    parameters: dict[str, Any]
    data_version: str = ""
    status: ExperimentStatus = ExperimentStatus.PENDING
    result: BacktestResult | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    tags: dict[str, str] = field(default_factory=dict)


class ExperimentEngine:
    def __init__(self) -> None:
        self._runs: list[ExperimentRun] = []

    def create_run(
        self,
        run_id: str,
        strategy: str,
        parameters: dict[str, Any],
        data_version: str = "",
        tags: dict[str, str] | None = None,
    ) -> ExperimentRun:
        run = ExperimentRun(
            run_id=run_id,
            strategy=strategy,
            parameters=parameters,
            data_version=data_version,
            tags=tags or {},
        )
        self._runs.append(run)
        return run

    def start_run(self, run: ExperimentRun) -> None:
        run.status = ExperimentStatus.RUNNING
        run.started_at = datetime.now(UTC)

    def complete_run(self, run: ExperimentRun, result: BacktestResult) -> None:
        run.status = ExperimentStatus.COMPLETED
        run.result = result
        run.completed_at = datetime.now(UTC)

    def fail_run(self, run: ExperimentRun, error: str) -> None:
        run.status = ExperimentStatus.FAILED
        run.error = error
        run.completed_at = datetime.now(UTC)

    def get_runs(self, status: ExperimentStatus | None = None) -> list[ExperimentRun]:
        if status is None:
            return self._runs
        return [r for r in self._runs if r.status == status]

    def get_run(self, run_id: str) -> ExperimentRun | None:
        for run in self._runs:
            if run.run_id == run_id:
                return run
        return None

    def clear(self) -> None:
        self._runs.clear()


class GridSearch:
    def __init__(self, experiment_engine: ExperimentEngine) -> None:
        self._engine = experiment_engine

    def generate(
        self,
        strategy_name: str,
        param_grid: dict[str, list[Any]],
        data_version: str = "",
    ) -> list[ExperimentRun]:
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        runs: list[ExperimentRun] = []
        for i, combination in enumerate(itertools.product(*values)):
            params = dict(zip(keys, combination, strict=False))
            run = self._engine.create_run(
                run_id=f"{strategy_name}_grid_{i}",
                strategy=strategy_name,
                parameters=params,
                data_version=data_version,
            )
            runs.append(run)
        return runs


class WalkForward:
    def __init__(self, experiment_engine: ExperimentEngine, n_windows: int = 5, train_pct: float = 0.7) -> None:
        self._engine = experiment_engine
        self.n_windows = n_windows
        self.train_pct = train_pct

    def generate(
        self,
        strategy_name: str,
        base_params: dict[str, Any],
        data_version: str = "",
    ) -> list[ExperimentRun]:
        runs: list[ExperimentRun] = []
        for window in range(self.n_windows):
            params = {
                **base_params,
                "window": window,
                "train_pct": self.train_pct,
                "test_pct": 1.0 - self.train_pct,
            }
            run = self._engine.create_run(
                run_id=f"{strategy_name}_wf_{window}",
                strategy=strategy_name,
                parameters=params,
                data_version=data_version,
                tags={"method": "walk_forward", "window": str(window)},
            )
            runs.append(run)
        return runs


class MonteCarlo:
    def __init__(self, experiment_engine: ExperimentEngine, n_simulations: int = 1000) -> None:
        self._engine = experiment_engine
        self.n_simulations = n_simulations

    def generate(
        self,
        strategy_name: str,
        param_distributions: dict[str, tuple[float, float]],
        data_version: str = "",
        seed: int = 42,
    ) -> list[ExperimentRun]:
        rng = random.Random(seed)
        runs: list[ExperimentRun] = []
        for i in range(self.n_simulations):
            params: dict[str, Any] = {}
            for key, (low, high) in param_distributions.items():
                params[key] = low + (high - low) * rng.random()
            run = self._engine.create_run(
                run_id=f"{strategy_name}_mc_{i}",
                strategy=strategy_name,
                parameters=params,
                data_version=data_version,
                tags={"method": "monte_carlo", "simulation": str(i)},
            )
            runs.append(run)
        return runs
