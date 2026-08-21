"""Portfolio Ledger — double-entry accounting for backtesting.

Handles:
- Cash management with settlement delay (T+0/T+1/T+2)
- Blocked cash for pending orders
- Realized / unrealized PnL tracking
- Fee and tax ledger
- Corporate action impact on positions
- Blocked cash during settlement
- Buying power calculation
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class EntryType(StrEnum):
    BUY = "buy"
    SELL = "sell"
    COMMISSION = "commission"
    TAX = "tax"
    DIVIDEND = "dividend"
    CAPITAL_INCREASE = "capital_increase"
    INTEREST = "interest"
    FEE = "fee"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"


@dataclass
class LedgerEntry:
    """A single accounting entry."""
    entry_id: str = ""
    entry_type: EntryType = EntryType.BUY
    symbol: str = ""
    quantity: int = 0
    price: float = 0.0
    amount: float = 0.0  # quantity * price (+ fees for buy, - fees for sell)
    fee: float = 0.0
    tax: float = 0.0
    commission: float = 0.0
    settlement_date: date | None = None
    timestamp: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PositionLot:
    """A tax lot for a position (FIFO tracking)."""
    symbol: str = ""
    quantity: int = 0
    avg_cost: float = 0.0
    entry_date: date | None = None
    entry_price: float = 0.0


@dataclass
class BlockedCash:
    """Cash blocked for pending buy orders."""
    order_id: str = ""
    symbol: str = ""
    amount: float = 0.0
    blocked_at: date | None = None
    release_at: date | None = None  # settlement date


class PortfolioLedger:
    """Double-entry portfolio accounting with settlement support.

    Tracks:
    - Available cash vs blocked cash vs total cash
    - Position lots (FIFO) for tax calculation
    - Pending settlement (T+2 for stocks)
    - Fee/tax breakdown
    - Realized vs unrealized PnL
    """

    def __init__(
        self,
        initial_capital: float = 1_000_000_000,
        commission_pct: float = 0.0003,
        tax_pct: float = 0.0005,
        settlement_days: int = 2,
    ) -> None:
        self._initial_capital = initial_capital
        self._cash = initial_capital
        self._commission_pct = commission_pct
        self._tax_pct = tax_pct
        self._settlement_days = settlement_days

        # Accounting
        self._entries: list[LedgerEntry] = []
        self._positions: dict[str, list[PositionLot]] = {}
        self._blocked_cash: list[BlockedCash] = []
        self._current_date: date | None = None

        # Tracking
        self._total_commission = 0.0
        self._total_tax = 0.0
        self._realized_pnl = 0.0

    def set_date(self, current_date: date) -> None:
        """Update current date — releases settled cash."""
        self._current_date = current_date
        self._release_settled_cash(current_date)

    def get_cash(self) -> float:
        return self._cash

    def get_blocked_cash(self) -> float:
        return sum(b.amount for b in self._blocked_cash)

    def get_available_cash(self) -> float:
        return self._cash - self.get_blocked_cash()

    def get_positions(self) -> dict[str, int]:
        """Get current positions (symbol -> quantity)."""
        result = {}
        for symbol, lots in self._positions.items():
            total = sum(lot.quantity for lot in lots)
            if total != 0:
                result[symbol] = total
        return result

    def get_position_value(self, prices: dict[str, float]) -> float:
        """Calculate total unrealized position value."""
        value = 0.0
        for symbol, lots in self._positions.items():
            price = prices.get(symbol, 0.0)
            qty = sum(lot.quantity for lot in lots)
            value += qty * price
        return value

    def get_nav(self, prices: dict[str, float]) -> float:
        """Net Asset Value = cash + position value."""
        return self._cash + self.get_position_value(prices)

    def buy(
        self, symbol: str, quantity: int, price: float, current_date: date
    ) -> LedgerEntry | None:
        """Record a buy transaction."""
        if quantity <= 0 or price <= 0:
            return None

        amount = quantity * price
        commission = amount * self._commission_pct
        total_cost = amount + commission

        if total_cost > self.get_available_cash():
            logger.warning("Insufficient cash for buy %s: need %.2f, have %.2f", symbol, total_cost, self.get_available_cash())
            return None

        # Deduct cash
        self._cash -= total_cost

        # Add to positions (FIFO lot)
        # Keep the buy-side commission in the lot cost basis.  This makes
        # realized PnL net of both entry and exit costs instead of reporting a
        # gross number that disagrees with the cash balance.
        lot = PositionLot(
            symbol=symbol,
            quantity=quantity,
            avg_cost=total_cost / quantity,
            entry_date=current_date,
            entry_price=price,
        )
        if symbol not in self._positions:
            self._positions[symbol] = []
        self._positions[symbol].append(lot)

        # Record entry
        entry = LedgerEntry(
            entry_id=f"buy_{int(time.time()*1000)}",
            entry_type=EntryType.BUY,
            symbol=symbol,
            quantity=quantity,
            price=price,
            amount=amount,
            commission=commission,
            settlement_date=self._add_settlement_days(current_date),
            timestamp=time.time(),
        )
        self._entries.append(entry)
        self._total_commission += commission

        return entry

    def sell(
        self, symbol: str, quantity: int, price: float, current_date: date
    ) -> LedgerEntry | None:
        """Record a sell transaction (FIFO lot matching)."""
        if quantity <= 0 or price <= 0:
            return None

        # Check if we have enough position
        lots = self._positions.get(symbol, [])
        total_held = sum(lot.quantity for lot in lots)
        if quantity > total_held:
            logger.warning("Insufficient position for sell %s: need %d, have %d", symbol, quantity, total_held)
            return None

        amount = quantity * price
        commission = amount * self._commission_pct
        tax = amount * self._tax_pct
        net_proceeds = amount - commission - tax

        # FIFO lot matching for realized PnL
        remaining = quantity
        realized = 0.0
        new_lots = []
        for lot in lots:
            if remaining <= 0:
                new_lots.append(lot)
                continue
            fill_qty = min(lot.quantity, remaining)
            realized += fill_qty * (price - lot.avg_cost)
            lot.quantity -= fill_qty
            remaining -= fill_qty
            if lot.quantity > 0:
                new_lots.append(lot)
        self._positions[symbol] = new_lots

        # Add cash (settlement delay)
        self._cash += net_proceeds
        # ``avg_cost`` already contains the proportional buy commission;
        # subtract the sell-side commission and tax from realized PnL too so
        # ledger PnL reconciles with NAV/cash.
        self._realized_pnl += realized - commission - tax

        # Record entry
        entry = LedgerEntry(
            entry_id=f"sell_{int(time.time()*1000)}",
            entry_type=EntryType.SELL,
            symbol=symbol,
            quantity=quantity,
            price=price,
            amount=amount,
            commission=commission,
            tax=tax,
            settlement_date=self._add_settlement_days(current_date),
            timestamp=time.time(),
        )
        self._entries.append(entry)
        self._total_commission += commission
        self._total_tax += tax

        return entry

    def block_cash(self, order_id: str, symbol: str, amount: float) -> None:
        """Block cash for a pending order."""
        self._blocked_cash.append(BlockedCash(
            order_id=order_id, symbol=symbol, amount=amount,
            blocked_at=self._current_date,
        ))

    def release_cash(self, order_id: str) -> None:
        """Release blocked cash (on order cancel/reject)."""
        self._blocked_cash = [b for b in self._blocked_cash if b.order_id != order_id]

    def apply_dividend(self, symbol: str, dividend_per_share: float, current_date: date) -> None:
        """Apply cash dividend to held position."""
        lots = self._positions.get(symbol, [])
        total_shares = sum(lot.quantity for lot in lots)
        if total_shares <= 0:
            return
        dividend_amount = total_shares * dividend_per_share
        self._cash += dividend_amount
        entry = LedgerEntry(
            entry_type=EntryType.DIVIDEND, symbol=symbol,
            quantity=total_shares, price=dividend_per_share,
            amount=dividend_amount, timestamp=time.time(),
        )
        self._entries.append(entry)

    def apply_capital_increase_retained(self, symbol: str, ratio: float, current_date: date) -> None:
        """Apply a retained-earnings increase without creating fake PnL.

        The total cost of a lot is unchanged.  When the share count rises,
        the per-share cost must fall by the same old/new quantity ratio.
        """
        if ratio <= 0:
            raise ValueError("capital increase ratio must be positive")

        lots = self._positions.get(symbol, [])
        total_old = 0
        total_new = 0
        for lot in lots:
            old_quantity = lot.quantity
            bonus = int(old_quantity * (ratio - 1))
            new_quantity = old_quantity + bonus
            if new_quantity <= 0:
                continue
            lot.quantity = new_quantity
            lot.avg_cost *= old_quantity / new_quantity
            lot.entry_price *= old_quantity / new_quantity
            total_old += old_quantity
            total_new += new_quantity

        if total_old and total_new != total_old:
            self._entries.append(LedgerEntry(
                entry_id=f"capital_increase_{int(time.time() * 1000)}",
                entry_type=EntryType.CAPITAL_INCREASE,
                symbol=symbol,
                quantity=total_new - total_old,
                timestamp=time.time(),
                metadata={
                    "ratio": ratio,
                    "effective_ratio": total_new / total_old,
                    "event_date": current_date.isoformat(),
                },
            ))

    def get_realized_pnl(self) -> float:
        return self._realized_pnl

    def get_total_fees(self) -> float:
        return self._total_commission + self._total_tax

    def get_summary(self, prices: dict[str, float] | None = None) -> dict[str, Any]:
        """Get a summary of the portfolio state."""
        pos = self.get_positions()
        nav = self.get_nav(prices) if prices else self._cash
        return {
            "cash": round(self._cash, 2),
            "blocked_cash": round(self.get_blocked_cash(), 2),
            "available_cash": round(self.get_available_cash(), 2),
            "positions": pos,
            "position_value": round(self.get_position_value(prices or {}), 2) if prices else 0,
            "nav": round(nav, 2),
            "total_return_pct": round(((nav / self._initial_capital) - 1) * 100, 4),
            "realized_pnl": round(self._realized_pnl, 2),
            "total_commission": round(self._total_commission, 2),
            "total_tax": round(self._total_tax, 2),
            "total_fees": round(self.get_total_fees(), 2),
            "total_entries": len(self._entries),
        }

    def _release_settled_cash(self, current_date: date) -> None:
        """Release cash from settled transactions."""
        released = []
        remaining = []
        for b in self._blocked_cash:
            if b.release_at and current_date >= b.release_at:
                released.append(b)
            else:
                remaining.append(b)
        if released:
            self._blocked_cash = remaining

    def _add_settlement_days(self, d: date) -> date:
        """Add settlement days using the Tehran market weekend (Thu/Fri)."""
        from datetime import timedelta

        result = d
        days_added = 0
        while days_added < self._settlement_days:
            result += timedelta(days=1)
            # Python weekday: Thursday=3, Friday=4 in Iran's market calendar.
            if result.weekday() not in (3, 4):
                days_added += 1
        return result
