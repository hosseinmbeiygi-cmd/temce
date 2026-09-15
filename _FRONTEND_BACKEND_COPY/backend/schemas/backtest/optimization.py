from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class OptimizationConfig(BaseModel):
    method: str = "grid_search"
    max_iterations: int = 100
    target_metric: str = "sharpe_ratio"
    parallel_jobs: int = 4
    cv_folds: int = 3


class OptimizationRequest(BaseModel):
    strategy_type: str
    symbols: list[str]
    start_date: str
    end_date: str
    param_grid: dict[str, list[Any]] = Field(default_factory=dict)
    config: OptimizationConfig = Field(default_factory=OptimizationConfig)


class OptimizationResult(BaseModel):
    id: str
    strategy_type: str = ""
    best_params: dict[str, Any] = Field(default_factory=dict)
    best_metrics: dict[str, float] = Field(default_factory=dict)
    iterations_completed: int = 0
    total_iterations: int = 0
    duration_seconds: float = 0.0
    results_table: list[dict[str, Any]] = Field(default_factory=list)
    status: str = "completed"
