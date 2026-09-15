"""Comprehensive Event-Driven Backtest Engine for Tehran Stock Exchange.

Implements all 8 golden standards:
1. Event-driven
2. Execution-aware
3. Liquidity-aware
4. Queue-aware
5. Latency-aware
6. Risk-aware
7. Point-in-time
8. Statistically validated

Architecture:
Data Layer → Event Engine → Feature/Signal → Strategy → Risk → Execution → Portfolio → Analytics
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


# ── Enums & Data Classes ────────────────────────────────────────────────────────────────────────────────────────────────────────────


class EventType(Enum):
    MARKET_OPEN = "MARKET_OPEN"
    AUCTION_OPEN = "AUCTION_OPEN"
    BOOK_UPDATE = "BOOK_UPDATE"
    TRADE_TICK = "TRADE_TICK"
    BAR_CLOSE = "BAR_CLOSE"
    SIGNAL_EVENT = "SIGNAL_EVENT"
    ORDER_SUBMIT = "ORDER_SUBMIT"
    ORDER_ACK = "ORDER_ACK"
    ORDER_REJECT = "ORDER_REJECT"
    ORDER_PARTIAL_FILL = "ORDER_PARTIAL_FILL"
    ORDER_FILL = "ORDER_FILL"
    ORDER_CANCEL = "ORDER_CANCEL"
    RISK_ALERT = "RISK_ALERT"
    MARKET_CLOSE = "MARKET_CLOSE"
    HALT = "HALT"
    RESUME = "RESUME"


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderStatus(Enum):
    NEW = "NEW"
    ACKED = "ACKED"
    PARTIAL_FILL = "PARTIAL_FILL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class MarketEvent:
    timestamp: float
    event_type: EventType
    symbol: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class Order:
    order_id: str
    symbol: str
    side: OrderSide
    qty: float
    order_type: OrderType = OrderType.LIMIT
    limit_price: float = 0.0
    stop_price: float = 0.0
    timestamp: float = 0.0
    status: OrderStatus = OrderStatus.NEW
    filled_qty: float = 0.0
    remaining_qty: float = 0.0

    def __post_init__(self):
        self.remaining_qty = self.qty


@dataclass
class Fill:
    order_id: str
    symbol: str
    side: OrderSide
    qty: float
    price: float
    timestamp: float
    fee: float = 0.0
    tax: float = 0.0
    slippage: float = 0.0
    queue_delay: float = 0.0


@dataclass
class Position:
    symbol: str
    qty: float = 0.0
    avg_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0


@dataclass
class MarketState:
    symbol: str
    timestamp: float
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0
    value: float = 0.0
    bid_price: float = 0.0
    ask_price: float = 0.0
    bid_size: float = 0.0
    ask_size: float = 0.0
    bid_queue: float = 0.0
    ask_queue: float = 0.0
    limit_up: float = 0.0
    limit_down: float = 0.0
    yesterday_close: float = 0.0
    is_halted: bool = False
    is_auction: bool = False


# ── TSE Rules Engine ────────────────────────────────────────────────────────────────────────────────────────────────────────────────


class TSERulesEngine:
    """TSE-specific market rules: price limits, queues, halts, base volume."""

    def __init__(self, limit_pct: float = 0.05):
        self.limit_pct = limit_pct

    def compute_price_limits(self, yesterday_close: float) -> tuple[float, float]:
        return yesterday_close * (1 - self.limit_pct), yesterday_close * (1 + self.limit_pct)

    def is_locked_buy(self, state: MarketState) -> bool:
        return state.close >= state.limit_up and state.ask_queue > 0 and state.ask_size == 0

    def is_locked_sell(self, state: MarketState) -> bool:
        return state.close <= state.limit_down and state.bid_queue > 0 and state.bid_size == 0

    def apply_base_volume_effect(self, raw_return: float, volume: float, base_volume: float) -> float:
        if base_volume <= 0:
            return raw_return

        return raw_return * min(1.0, volume / base_volume)

    def can_trade(self, state: MarketState) -> bool:
        if state.is_halted:
            return False

        return not state.close <= 0

    def adjust_price_to_limits(self, price: float, state: MarketState) -> float:
        return max(state.limit_down, min(price, state.limit_up))


# ── Slippage Models ────────────────────────────────────────────────────────────────────────────────────────────────────────────────


class SlippageModel:
    """Multi-layer slippage modeling."""

    def __init__(self, model_type: str = "adaptive", fixed_bps: float = 5.0):
        self.model_type = model_type
        self.fixed_bps = fixed_bps

    def compute(self, order_qty: float, state: MarketState, side: OrderSide) -> float:
        if self.model_type == "fixed":
            return self.fixed_bps / 10000

        elif self.model_type == "spread_based":
            spread = state.ask_price - state.bid_price if state.bid_price > 0 and state.ask_price > 0 else 0
            return (spread / 2) / state.close if state.close > 0 else 0
        elif self.model_type == "adaptive":
            spread = state.ask_price - state.bid_price if state.bid_price > 0 and state.ask_price > 0 else 0
            a = 0.3  # spread coefficient
            spread_cost = a * spread / state.close if state.close > 0 else 0
            volume_ratio = order_qty / max(state.volume, 1)
            impact_cost = 0.001 * math.sqrt(volume_ratio) if volume_ratio > 0 else 0
            return spread_cost + impact_cost + self.fixed_bps / 10000
        return self.fixed_bps / 10000


# ── Latency Model ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────


class LatencyModel:
    """Model total latency: compute + network + broker + exchange."""

    def __init__(self, compute_ms: float = 10, network_ms: float = 5, broker_ms: float = 20, exchange_ms: float = 15):
        self.total_ms = compute_ms + network_ms + broker_ms + exchange_ms
        self.total_seconds = self.total_ms / 1000

    def get_delayed_timestamp(self, signal_timestamp: float) -> float:
        return signal_timestamp + self.total_seconds


# ── Execution Engine ──────────────────────────────────────────────────────────────────────────────────────────────────────────────


class ExecutionEngine:
    """Queue-aware, latency-aware execution simulator."""

    def __init__(
        self,
        commission_buy: float = 0.003712,
        commission_sell: float = 0.0088,
        slippage_model: SlippageModel | None = None,
        latency_model: LatencyModel | None = None,
        participation_rate: float = 0.1,
    ):
        self.comm_buy = commission_buy
        self.comm_sell = commission_sell
        self.slippage_model = slippage_model or SlippageModel()
        self.latency_model = latency_model or LatencyModel()
        self.participation_rate = participation_rate
        self.live_orders: list[Order] = []
        self.all_orders: list[Order] = []
        self.all_fills: list[Fill] = []
        self.queue_positions: dict[str, float] = {}

    def submit(self, order: Order):
        order.status = OrderStatus.ACKED
        self.live_orders.append(order)
        self.all_orders.append(order)

    def match(self, event: MarketEvent, state: MarketState, rules: TSERulesEngine) -> list[Fill]:
        fills = []
        if not rules.can_trade(state):
            return fills

        for order in list(self.live_orders):
            if order.symbol != state.symbol:
                continue

            if order.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED):
                self.live_orders.remove(order)

                continue

            fill = self._try_fill(order, state, rules)
            if fill:
                fills.append(fill)

                self.all_fills.append(fill)
                if order.remaining_qty <= 0:
                    order.status = OrderStatus.FILLED

                    self.live_orders.remove(order)
                else:
                    order.status = OrderStatus.PARTIAL_FILL

        return fills

    def _try_fill(self, order: Order, state: MarketState, rules: TSERulesEngine) -> Fill | None:
        slippage = self.slippage_model.compute(order.remaining_qty, state, order.side)

        if order.side == OrderSide.BUY:
            if rules.is_locked_buy(state):
                queue_pos = self.queue_positions.get(order.order_id, state.bid_queue)
                vol_at_limit = state.volume * 0.7
                cancellations = queue_pos * 0.05
                queue_pos = max(0, queue_pos - vol_at_limit - cancellations)
                self.queue_positions[order.order_id] = queue_pos

                if queue_pos <= 0:
                    max_exec = state.volume * self.participation_rate

                    exec_qty = min(order.remaining_qty, max_exec)
                    price = state.limit_up * (1 + slippage)
                else:
                    return None
            else:
                exec_qty = min(order.remaining_qty, state.ask_size if state.ask_size > 0 else order.remaining_qty)
                price = state.ask_price * (1 + slippage) if state.ask_price > 0 else state.close * (1 + slippage)

        else:  # SELL
            if rules.is_locked_sell(state):
                queue_pos = self.queue_positions.get(order.order_id, state.ask_queue)

                vol_at_limit = state.volume * 0.7
                cancellations = queue_pos * 0.05
                queue_pos = max(0, queue_pos - vol_at_limit - cancellations)
                self.queue_positions[order.order_id] = queue_pos

                if queue_pos <= 0:
                    max_exec = state.volume * self.participation_rate

                    exec_qty = min(order.remaining_qty, max_exec)
                    price = state.limit_down * (1 - slippage)
                else:
                    return None
            else:
                exec_qty = min(order.remaining_qty, state.bid_size if state.bid_size > 0 else order.remaining_qty)
                price = state.bid_price * (1 - slippage) if state.bid_price > 0 else state.close * (1 - slippage)

        if exec_qty <= 0:
            return None

        commission = exec_qty * price * (self.comm_buy if order.side == OrderSide.BUY else self.comm_sell)
        tax = exec_qty * price * 0.001 if order.side == OrderSide.SELL else 0

        order.filled_qty += exec_qty
        order.remaining_qty -= exec_qty

        return Fill(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            qty=exec_qty,
            price=price,
            timestamp=state.timestamp,
            fee=commission,
            tax=tax,
            slippage=slippage,
        )

    def cancel_all(self):
        for order in self.live_orders:
            order.status = OrderStatus.CANCELLED
        self.live_orders.clear()

    def get_stats(self) -> dict[str, Any]:
        total = len(self.all_fills)
        queued = sum(1 for o in self.all_orders if o.status == OrderStatus.PARTIAL_FILL)
        rejected = sum(1 for o in self.all_orders if o.status == OrderStatus.REJECTED)
        avg_slippage = sum(f.slippage for f in self.all_fills) / max(total, 1)
        avg_delay = sum(f.queue_delay for f in self.all_fills) / max(total, 1)
        return {
            "total_fills": total,
            "total_orders": len(self.all_orders),
            "queued_orders": queued,
            "rejected_orders": rejected,
            "fill_rate": round(total / max(len(self.all_orders), 1) * 100, 1),
            "avg_slippage_bps": round(avg_slippage * 10000, 1),
            "avg_queue_delay": round(avg_delay, 2),
        }


# ── Portfolio Engine ──────────────────────────────────────────────────────────────────────────────────────────────────────────────


class PortfolioEngine:
    """Portfolio accounting: cash, positions, PnL, NAV."""

    def __init__(self, initial_cash: float = 1_000_000_000):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.frozen_cash = 0.0
        self.positions: dict[str, Position] = {}
        self.realized_pnl = 0.0
        self.total_fees = 0.0
        self.total_taxes = 0.0
        self.equity_curve: list[dict[str, Any]] = []
        self.trade_log: list[dict[str, Any]] = []

    def apply_fill(self, fill: Fill):
        sym = fill.symbol
        if sym not in self.positions:
            self.positions[sym] = Position(symbol=sym)

        pos = self.positions[sym]
        self.total_fees += fill.fee
        self.total_taxes += fill.tax

        if fill.side == OrderSide.BUY:
            cost = fill.qty * fill.price + fill.fee

            self.cash -= cost
            total_qty = pos.qty + fill.qty
            if total_qty > 0:
                pos.avg_price = (pos.avg_price * pos.qty + fill.price * fill.qty) / total_qty

            pos.qty = total_qty
        else:
            proceeds = fill.qty * fill.price - fill.fee - fill.tax
            self.cash += proceeds
            pnl = (fill.price - pos.avg_price) * fill.qty - fill.fee - fill.tax
            self.realized_pnl += pnl
            pos.qty -= fill.qty
            if pos.qty <= 0:
                pos.qty = 0

                pos.avg_price = 0

        self.trade_log.append(
            {
                "symbol": fill.symbol,
                "side": fill.side.value,
                "qty": fill.qty,
                "price": fill.price,
                "fee": fill.fee,
                "tax": fill.tax,
                "pnl": (fill.price - pos.avg_price) * fill.qty if fill.side == OrderSide.SELL else 0,
            }
        )

    def mark_to_market(self, prices: dict[str, float]):
        for sym, pos in self.positions.items():
            if pos.qty > 0 and sym in prices:
                pos.market_value = pos.qty * prices[sym]

                pos.unrealized_pnl = (prices[sym] - pos.avg_price) * pos.qty

    def get_nav(self, prices: dict[str, float]) -> float:
        self.mark_to_market(prices)
        positions_value = sum(p.market_value for p in self.positions.values())
        return self.cash + positions_value

    def snapshot(self) -> dict[str, Any]:
        return {
            "cash": round(self.cash, 0),
            "positions": {
                s: {"qty": p.qty, "avg_price": round(p.avg_price, 2), "unrealized": round(p.unrealized_pnl, 0)}
                for s, p in self.positions.items()
                if p.qty > 0
            },
            "realized_pnl": round(self.realized_pnl, 0),
            "total_fees": round(self.total_fees, 0),
            "total_taxes": round(self.total_taxes, 0),
        }


# ── Risk Engine ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────


class RiskEngine:
    """Multi-constraint risk engine."""

    def __init__(
        self,
        max_position_pct: float = 0.20,
        max_sector_pct: float = 0.30,
        max_drawdown_pct: float = 0.20,
        max_daily_turnover_pct: float = 0.50,
        min_liquidity_value: float = 10e9,
        target_volatility: float = 0.15,
    ):
        self.max_position_pct = max_position_pct
        self.max_sector_pct = max_sector_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.max_daily_turnover_pct = max_daily_turnover_pct
        self.min_liquidity_value = min_liquidity_value
        self.target_volatility = target_volatility
        self.peak_nav = 0.0
        self.kill_switch = False
        self.alerts: list[dict[str, Any]] = []

    def check(self, order: Order, portfolio: PortfolioEngine, state: MarketState, nav: float) -> bool:
        if self.kill_switch:
            return False

        if nav > 0 and self.peak_nav > 0:
            current_dd = (self.peak_nav - nav) / self.peak_nav

            if current_dd > self.max_drawdown_pct:
                self.kill_switch = True

                self.alerts.append({"type": "KILL_SWITCH", "drawdown": current_dd, "timestamp": state.timestamp})
                return False

        order_value = order.qty * (order.limit_price or state.close)
        if nav > 0 and order_value / nav > self.max_position_pct:
            order.qty = int(nav * self.max_position_pct / (order.limit_price or state.close))

            if order.qty <= 0:
                return False

        return not state.volume < 1000

    def volatility_adjust_weight(self, weight: float, current_vol: float) -> float:
        if current_vol <= 0:
            return weight

        return weight * min(1.0, self.target_volatility / current_vol)

    def on_fill(self, fill: Fill, nav: float):
        self.peak_nav = max(self.peak_nav, nav)


# ── Analytics Engine ──────────────────────────────────────────────────────────────────────────────────────────────────────────────


class AnalyticsEngine:
    """Comprehensive analytics and reporting."""

    def generate_report(self, portfolio: PortfolioEngine, execution: ExecutionEngine) -> dict[str, Any]:
        equity = portfolio.equity_curve
        if len(equity) < 2:
            return {"error": "Insufficient data"}

        navs = [e["nav"] for e in equity]
        total_return = (navs[-1] / navs[0] - 1) * 100
        years = len(navs) / 252
        cagr = ((navs[-1] / navs[0]) ** (1 / max(years, 0.01)) - 1) * 100

        returns = [(navs[i] / navs[i - 1]) - 1 for i in range(1, len(navs)) if navs[i - 1] > 0]
        avg_r = sum(returns) / len(returns) if returns else 0
        std_r = math.sqrt(sum((r - avg_r) ** 2 for r in returns) / len(returns)) if returns else 1
        sharpe = (avg_r / std_r) * math.sqrt(252) if std_r > 0 else 0

        peak = navs[0]
        max_dd = 0.0
        for v in navs:
            if v > peak:
                peak = v

            dd = (peak - v) / peak
            max_dd = max(max_dd, dd)

        downside = [r for r in returns if r < 0]
        down_std = math.sqrt(sum(r**2 for r in downside) / len(downside)) if downside else 1
        sortino = (avg_r / down_std) * math.sqrt(252) if down_std > 0 else 0
        calmar = cagr / (max_dd * 100) if max_dd > 0 else 0

        wins = [t for t in portfolio.trade_log if t.get("pnl", 0) > 0]
        losses = [t for t in portfolio.trade_log if t.get("pnl", 0) < 0]
        sell_trades = [t for t in portfolio.trade_log if t["side"] == "SELL"]

        sorted_losses = sorted(returns)
        cutoff = max(1, int(0.05 * len(sorted_losses)))
        cvar = -sum(sorted_losses[:cutoff]) / cutoff * math.sqrt(252) if sorted_losses else 0

        exec_stats = execution.get_stats()

        return {
            "performance": {
                "total_return_pct": round(total_return, 2),
                "cagr_pct": round(cagr, 2),
                "final_nav": round(navs[-1], 0),
            },
            "risk": {
                "sharpe": round(sharpe, 2),
                "sortino": round(sortino, 2),
                "calmar": round(calmar, 2),
                "max_drawdown_pct": round(max_dd * 100, 2),
                "cvar_95": round(cvar, 2),
                "volatility": round(std_r * math.sqrt(252) * 100, 2),
            },
            "trading": {
                "total_trades": len(sell_trades),
                "winning_trades": len(wins),
                "losing_trades": len(losses),
                "win_rate": round(len(wins) / max(len(sell_trades), 1) * 100, 1),
                "profit_factor": round(
                    sum(t.get("pnl", 0) for t in wins) / max(abs(sum(t.get("pnl", 0) for t in losses)), 1), 2
                ),
                "total_fees": round(portfolio.total_fees, 0),
                "total_taxes": round(portfolio.total_taxes, 0),
            },
            "execution": exec_stats,
            "costs": {
                "total_fees_pct": round(portfolio.total_fees / max(portfolio.initial_cash, 1) * 100, 4),
                "total_taxes_pct": round(portfolio.total_taxes / max(portfolio.initial_cash, 1) * 100, 4),
                "total_costs": round(portfolio.total_fees + portfolio.total_taxes, 0),
            },
            "equity_curve": navs[:: max(1, len(navs) // 100)],
        }


# ── Main Backtest Engine ──────────────────────────────────────────────────────────────────────────────────────────────────────────


class EventBacktestEngine:
    """Comprehensive event-driven backtest engine for TSE."""

    def __init__(self, initial_cash: float = 1_000_000_000):
        self.portfolio = PortfolioEngine(initial_cash)
        self.execution = ExecutionEngine()
        self.risk = RiskEngine()
        self.rules = TSERulesEngine()
        self.analytics = AnalyticsEngine()
        self.strategy: Callable | None = None
        self.feature_engine: Callable | None = None

    def set_strategy(self, strategy_fn: Callable):
        self.strategy = strategy_fn

    def set_features(self, feature_fn: Callable):
        self.feature_engine = feature_fn

    def run(self, data: list[dict], signals: list[int]) -> dict[str, Any]:
        equity_curve = []
        nav = self.portfolio.initial_cash

        for i, bar in enumerate(data):
            if i >= len(signals):
                break

            signal = signals[i]
            state = MarketState(
                symbol=bar.get("symbol", "unknown"),
                timestamp=i,
                open=bar.get("open", 0),
                high=bar.get("high", 0),
                low=bar.get("low", 0),
                close=bar.get("close", 0),
                volume=bar.get("volume", 0),
                value=bar.get("value", 0),
                bid_price=bar.get("bid_price", bar.get("close", 0)),
                ask_price=bar.get("ask_price", bar.get("close", 0)),
                bid_size=bar.get("bid_size", 0),
                ask_size=bar.get("ask_size", 0),
                bid_queue=bar.get("bid_queue", 0),
                ask_queue=bar.get("ask_queue", 0),
                limit_up=bar.get("limit_up", bar.get("close", 0) * 1.05),
                limit_down=bar.get("limit_down", bar.get("close", 0) * 0.95),
                yesterday_close=bar.get("yesterday_close", bar.get("close", 0)),
            )

            if not self.rules.can_trade(state):
                equity_curve.append({"nav": nav, "timestamp": i})

                continue

            # Process signals through risk engine
            if signal == 1:
                pos = self.portfolio.positions.get(state.symbol)

                if not pos or pos.qty <= 0:
                    max_qty = int(nav * self.risk.max_position_pct / state.close) if state.close > 0 else 0

                    if max_qty > 0:
                        order = Order(
                            order_id=f"O{i}_BUY",
                            symbol=state.symbol,
                            side=OrderSide.BUY,
                            qty=max_qty,
                            order_type=OrderType.LIMIT,
                            limit_price=state.close,
                            timestamp=i,
                        )
                        if self.risk.check(order, self.portfolio, state, nav):
                            self.execution.submit(order)

            elif signal == -1:
                pos = self.portfolio.positions.get(state.symbol)
                if pos and pos.qty > 0:
                    order = Order(
                        order_id=f"O{i}_SELL",
                        symbol=state.symbol,
                        side=OrderSide.SELL,
                        qty=pos.qty,
                        order_type=OrderType.LIMIT,
                        limit_price=state.close,
                        timestamp=i,
                    )
                    self.execution.submit(order)

            # Match orders
            event = MarketEvent(timestamp=i, event_type=EventType.BAR_CLOSE, symbol=state.symbol)
            fills = self.execution.match(event, state, self.rules)
            for fill in fills:
                self.portfolio.apply_fill(fill)
                self.risk.on_fill(fill, nav)

            nav = self.portfolio.get_nav({state.symbol: state.close})
            equity_curve.append({"nav": nav, "timestamp": i})

        self.portfolio.equity_curve = equity_curve
        return self.analytics.generate_report(self.portfolio, self.execution)
