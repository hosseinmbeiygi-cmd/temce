"""Pydantic request models for backtests endpoints.

Kept in a separate module so they can be imported by tests without dragging in
the full backtests router. The field names mirror the legacy ``body.get(...)``
calls so existing clients continue to work unchanged.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _BaseBody(BaseModel):
    """Common configuration for body models.

    ``extra='ignore'`` keeps the contract backward-compatible — clients that
    send additional unknown fields still get a 200, not a 422. ``populate_by_name``
    is left at default since we mirror the existing JSON keys exactly.
    """

    model_config = ConfigDict(extra="ignore")


class RunOnAllSymbolsRequest(_BaseBody):
    strategy_type: str = "moving_average_cross"
    strategy_params: dict[str, Any] = Field(default_factory=dict)
    start_date: str | None = None
    end_date: str | None = None
    initial_capital: float = 1_000_000_000


class SaveCompareRequest(_BaseBody):
    symbol: str = ""
    total_strategies: int = 0
    successful: int = 0
    failed: int = 0
    best: dict[str, Any] | None = None
    worst: dict[str, Any] | None = None
    results: list[Any] = Field(default_factory=list)
    best_return_pct: float | None = None
    worst_return_pct: float | None = None
    avg_return_pct: float | None = None
    start_date: str | None = None
    end_date: str | None = None
    capital: float | None = None


class CompareStrategiesRequest(_BaseBody):
    symbol: str = "فولاد"
    start_date: str | None = None
    end_date: str | None = None
    initial_capital: float = 1_000_000_000


class ScanIndicatorsRequest(_BaseBody):
    symbols: list[str] | None = None
    indicator_ids: list[str] | None = None
    filters: dict[str, Any] | None = None
    start_date: str | None = None
    end_date: str | None = None
    capital: float = 1_000_000_000


class AdaptiveDecideRequest(_BaseBody):
    market_data: dict[str, Any] = Field(default_factory=dict)
    portfolio_returns: list[float] = Field(default_factory=list)
