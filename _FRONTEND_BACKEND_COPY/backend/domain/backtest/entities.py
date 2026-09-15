from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from domain.common.base_entity import BaseEntity
from domain.common.enum_types import OrderSide, OrderType


@dataclass
class BacktestRun(BaseEntity):
    name: str
    strategy_name: str = ""
    instrument_ids: list[str] = field(default_factory=list)
    start_date: date | None = None
    end_date: date | None = None
    initial_capital: float = 1000000.0
    current_capital: float = 0.0
    total_pnl: float = 0.0
    total_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    status: str = "draft"
    parameters: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        name: str,
        strategy_name: str = "",
        instrument_ids: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        initial_capital: float = 1000000.0,
        current_capital: float = 0.0,
        total_pnl: float = 0.0,
        total_return_pct: float = 0.0,
        sharpe_ratio: float = 0.0,
        max_drawdown: float = 0.0,
        win_rate: float = 0.0,
        total_trades: int = 0,
        status: str = "draft",
        parameters: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.name = name
        self.strategy_name = strategy_name
        self.instrument_ids = instrument_ids or []
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.current_capital = current_capital
        self.total_pnl = total_pnl
        self.total_return_pct = total_return_pct
        self.sharpe_ratio = sharpe_ratio
        self.max_drawdown = max_drawdown
        self.win_rate = win_rate
        self.total_trades = total_trades
        self.status = status
        self.parameters = parameters or {}
        self.extra = extra or {}

    def start(self) -> None:
        self.status = "running"
        self.mark_updated()

    def complete(self) -> None:
        self.status = "completed"
        self.mark_updated()

    def fail(self) -> None:
        self.status = "failed"
        self.mark_updated()


@dataclass
class Order(BaseEntity):
    backtest_run_id: str
    instrument_id: str
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    symbol: str = ""
    quantity: int = 0
    price: float = 0.0
    filled_quantity: int = 0
    filled_price: float = 0.0
    status: str = "pending"
    date: str = ""
    time: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        backtest_run_id: str,
        instrument_id: str,
        side: OrderSide,
        order_type: OrderType = OrderType.MARKET,
        symbol: str = "",
        quantity: int = 0,
        price: float = 0.0,
        filled_quantity: int = 0,
        filled_price: float = 0.0,
        status: str = "pending",
        date: str = "",
        time: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.backtest_run_id = backtest_run_id
        self.instrument_id = instrument_id
        self.side = side
        self.order_type = order_type
        self.symbol = symbol
        self.quantity = quantity
        self.price = price
        self.filled_quantity = filled_quantity
        self.filled_price = filled_price
        self.status = status
        self.date = date
        self.time = time
        self.extra = extra or {}

    @property
    def is_filled(self) -> bool:
        return self.status == "filled"

    @property
    def is_pending(self) -> bool:
        return self.status == "pending"

    def fill(self, fill_price: float, fill_quantity: int) -> None:
        self.filled_price = fill_price
        self.filled_quantity = fill_quantity
        self.status = "filled"
        self.mark_updated()

    def cancel(self) -> None:
        self.status = "cancelled"
        self.mark_updated()


@dataclass
class Fill(BaseEntity):
    order_id: str
    backtest_run_id: str
    instrument_id: str
    side: OrderSide
    symbol: str = ""
    price: float = 0.0
    quantity: int = 0
    value: float = 0.0
    commission: float = 0.0
    date: str = ""
    time: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        order_id: str,
        backtest_run_id: str,
        instrument_id: str,
        side: OrderSide,
        symbol: str = "",
        price: float = 0.0,
        quantity: int = 0,
        value: float = 0.0,
        commission: float = 0.0,
        date: str = "",
        time: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.order_id = order_id
        self.backtest_run_id = backtest_run_id
        self.instrument_id = instrument_id
        self.side = side
        self.symbol = symbol
        self.price = price
        self.quantity = quantity
        self.value = value
        self.commission = commission
        self.date = date
        self.time = time
        self.extra = extra or {}

    @property
    def net_value(self) -> float:
        return self.value - self.commission


@dataclass
class PerformanceSnapshot(BaseEntity):
    backtest_run_id: str
    date: str = ""
    equity: float = 0.0
    cash: float = 0.0
    nav: float = 0.0
    pnl: float = 0.0
    return_pct: float = 0.0
    drawdown: float = 0.0
    total_trades: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        backtest_run_id: str,
        date: str = "",
        equity: float = 0.0,
        cash: float = 0.0,
        nav: float = 0.0,
        pnl: float = 0.0,
        return_pct: float = 0.0,
        drawdown: float = 0.0,
        total_trades: int = 0,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.backtest_run_id = backtest_run_id
        self.date = date
        self.equity = equity
        self.cash = cash
        self.nav = nav
        self.pnl = pnl
        self.return_pct = return_pct
        self.drawdown = drawdown
        self.total_trades = total_trades
        self.extra = extra or {}
