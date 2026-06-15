from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from domain.common.enum_types import OrderSide, OrderType


@dataclass
class OrderEvent:
    instrument_id: str
    side: OrderSide
    quantity: int
    price: float = 0.0
    order_type: OrderType = OrderType.MARKET
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    order_id: str = ""


@dataclass
class FillEvent:
    order_id: str
    instrument_id: str
    side: OrderSide
    quantity: int
    price: float
    commission: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    slippage: float = 0.0


@dataclass
class PositionState:
    instrument_id: str
    quantity: int = 0
    avg_price: float = 0.0
    realized_pnl: float = 0.0


@dataclass
class EquityPoint:
    timestamp: datetime
    nav: float
    cash: float
    positions_value: float


@dataclass
class BacktestResult:
    strategy_name: str = ""
    initial_capital: float = 0.0
    final_capital: float = 0.0
    total_return: float = 0.0
    total_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    total_trades: int = 0
    win_rate: float = 0.0
    equity_curve: list[EquityPoint] = field(default_factory=list)
    trades: list[FillEvent] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    completed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
