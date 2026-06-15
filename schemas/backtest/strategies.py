from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StrategyParameter(BaseModel):
    name: str
    type: str = "float"
    default: Any = None
    min_value: float | None = None
    max_value: float | None = None
    description: str = ""


class StrategyDefinition(BaseModel):
    id: str
    name: str = ""
    description: str = ""
    parameters: list[StrategyParameter] = Field(default_factory=list)
    supported_timeframes: list[str] = Field(default_factory=lambda: ["1d"])
    asset_classes: list[str] = Field(default_factory=list)


class StrategyConfig(BaseModel):
    strategy_type: str
    params: dict[str, Any] = Field(default_factory=dict)
    timeframe: str = "1d"
    position_size_pct: float = 100.0
    max_positions: int = 1
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
