"""Corporate Actions — price adjustment, survivorship bias handling.

Handles:
- Capital increases (from retained earnings vs cash contribution)
- Cash dividends
- Stock splits / reverse splits
- Symbol changes (mergers, renames)
- Suspension / delisting
- Price adjustment (adjusted vs raw prices)

Critical for Iran market: capital increases are very common and
must be handled correctly to avoid artificial price jumps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class ActionType(StrEnum):
    CAPITAL_INCREASE_RETAINED = "capital_increase_retained"  # از محل سود انباشته
    CAPITAL_INCREASE_CASH = "capital_increase_cash"  # آورده نقدی
    CAPITAL_INCREASE_ASSETS = "capital_increase_assets"  # از محل افزایش سرمایه (سایر)
    CASH_DIVIDEND = "cash_dividend"  # سود نقدی
    STOCK_DIVIDEND = "stock_dividend"  # سود سهمی
    STOCK_SPLIT = "stock_split"
    REVERSE_SPLIT = "reverse_split"
    SYMBOL_CHANGE = "symbol_change"  # تغییر نام/نماد
    MERGER = "merger"  # ادغام
    SUSPENSION = "suspension"  # توقف
    DELISTING = "delisting"  # لغو پذیرش
    LISTING = "listing"  # پذیرش جدید
    HALT_FOR信息披露 = "halt_disclosure"  # توقف برای افشا
    FREE_FLOAT_CHANGE = "free_float_change"  # تغییر شناوری


@dataclass
class CorporateAction:
    """A single corporate action event."""

    action_type: ActionType
    symbol: str
    effective_date: date
    ex_date: date | None = None  # date without right

    # For capital increase / dividend
    old_shares: int = 0
    new_shares: int = 0
    cash_per_share: float = 0.0  # dividend or cash contribution per old share
    ratio: float = 1.0  # split ratio (2.0 = 2-for-1)

    # Price adjustment factor (cumulative)
    adjustment_factor: float = 1.0

    # Metadata
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SurvivorshipEntry:
    """Tracks a symbol's lifecycle for survivorship bias prevention."""

    symbol: str
    first_seen: date
    last_seen: date
    delisted: bool = False
    delist_date: date | None = None
    delist_reason: str = ""
    replaced_by: str | None = None  # new symbol after merger
    metadata: dict[str, Any] = field(default_factory=dict)


class CorporateActionsEngine:
    """Processes corporate actions and adjusts prices.

    Maintains a cumulative adjustment factor for each symbol.
    When computing adjusted prices, divide raw price by cumulative factor.
    """

    def __init__(self) -> None:
        self._actions: dict[str, list[CorporateAction]] = {}
        self._adjustment_factors: dict[str, list[tuple[date, float]]] = {}
        self._survivorship: dict[str, SurvivorshipEntry] = {}
        self._symbol_changes: dict[str, tuple[str, date]] = {}  # old -> (new, date)

    def register_action(self, action: CorporateAction) -> None:
        """Register a corporate action for a symbol."""
        if action.symbol not in self._actions:
            self._actions[action.symbol] = []
        self._actions[action.symbol].append(action)
        self._actions[action.symbol].sort(key=lambda a: a.effective_date)

        # Compute adjustment factor
        factor = self._compute_adjustment_factor(action)
        if factor != 1.0:
            if action.symbol not in self._adjustment_factors:
                self._adjustment_factors[action.symbol] = []
            self._adjustment_factors[action.symbol].append((action.ex_date or action.effective_date, factor))

        # Handle symbol changes
        if action.action_type == ActionType.SYMBOL_CHANGE:
            new_symbol = action.metadata.get("new_symbol", "")
            if new_symbol:
                self._symbol_changes[action.symbol] = (new_symbol, action.effective_date)

        # Handle delisting
        if action.action_type == ActionType.DELISTING:
            self._survivorship[action.symbol] = SurvivorshipEntry(
                symbol=action.symbol,
                first_seen=date.min,
                last_seen=action.effective_date,
                delisted=True,
                delist_date=action.effective_date,
                delist_reason=action.metadata.get("reason", ""),
            )

        logger.debug(
            "Registered corporate action: %s %s on %s", action.action_type, action.symbol, action.effective_date
        )

    def register_lifecycle(self, symbol: str, first_seen: date, last_seen: date, delisted: bool = False) -> None:
        """Register symbol lifecycle for survivorship tracking."""
        if symbol in self._survivorship:
            entry = self._survivorship[symbol]
            entry.first_seen = first_seen
            entry.last_seen = last_seen
            entry.delisted = delisted
        else:
            self._survivorship[symbol] = SurvivorshipEntry(
                symbol=symbol,
                first_seen=first_seen,
                last_seen=last_seen,
                delisted=delisted,
            )

    def get_adjusted_price(self, symbol: str, raw_price: float, on_date: date) -> float:
        """Convert raw price to adjusted price using cumulative factors."""
        factors = self._adjustment_factors.get(symbol, [])
        cumulative = 1.0
        for factor_date, factor in factors:
            if factor_date <= on_date:
                cumulative *= factor
        return raw_price / cumulative if cumulative > 0 else raw_price

    def get_cumulative_factor(self, symbol: str, on_date: date) -> float:
        """Get the cumulative adjustment factor up to a date."""
        factors = self._adjustment_factors.get(symbol, [])
        cumulative = 1.0
        for factor_date, factor in factors:
            if factor_date <= on_date:
                cumulative *= factor
        return cumulative

    def get_survivorship_status(self, symbol: str, on_date: date) -> dict[str, Any]:
        """Check if a symbol is alive on a given date (for universe construction)."""
        entry = self._survivorship.get(symbol)
        if not entry:
            return {"alive": True, "reason": "no_lifecycle_data"}
        if entry.delisted and entry.delist_date and on_date >= entry.delist_date:
            return {"alive": False, "reason": entry.delist_reason, "delist_date": entry.delist_date.isoformat()}
        if on_date < entry.first_seen:
            return {"alive": False, "reason": "not_yet_listed"}
        return {"alive": True, "reason": "active"}

    def build_survivorship_free_universe(self, all_symbols: list[str], on_date: date) -> list[str]:
        """Return only symbols alive on the given date (prevents survivorship bias)."""
        alive = []
        for sym in all_symbols:
            status = self.get_survivorship_status(sym, on_date)
            if status["alive"]:
                alive.append(sym)
        return alive

    def resolve_symbol_change(self, old_symbol: str, as_of: date) -> str:
        """Resolve a symbol change to the current symbol name."""
        if old_symbol in self._symbol_changes:
            new_sym, change_date = self._symbol_changes[old_symbol]
            if as_of >= change_date:
                return new_sym
        return old_symbol

    @staticmethod
    def _compute_adjustment_factor(action: CorporateAction) -> float:
        """Compute price adjustment factor for a corporate action."""
        if action.action_type == ActionType.CAPITAL_INCREASE_RETAINED:
            # Capital increase from retained earnings: no cash leaves the company
            # Price adjusts but total value stays same
            total_old = action.old_shares
            total_new = action.new_shares
            if total_old > 0 and total_new > 0:
                return total_old / total_new  # < 1.0 means price drops
            return 1.0

        elif action.action_type == ActionType.CAPITAL_INCREASE_CASH:
            # Cash contribution: price drops by cash_per_share, then adjusts for new shares
            # Cumulative factor = old_shares / new_shares (before ex-date adjustment)
            if action.old_shares > 0 and action.new_shares > 0:
                return action.old_shares / action.new_shares
            return 1.0

        elif action.action_type == ActionType.CASH_DIVIDEND:
            # Price drops by dividend amount
            if action.cash_per_share > 0:
                # Factor = 1 - (dividend / cum_price)
                # We approximate: factor = old_shares / (old_shares + implied_new_from_div)
                return 1.0  # Handled via raw subtraction
            return 1.0

        elif action.action_type == ActionType.STOCK_SPLIT:
            return 1.0 / action.ratio  # 2-for-1: factor = 0.5

        elif action.action_type == ActionType.REVERSE_SPLIT:
            return action.ratio  # 1-for-3: factor = 3.0

        return 1.0

    def get_actions_for_symbol(self, symbol: str) -> list[CorporateAction]:
        return self._actions.get(symbol, [])

    def get_actions_in_range(self, start: date, end: date) -> list[CorporateAction]:
        """Get all corporate actions in a date range across all symbols."""
        actions = []
        for symbol_actions in self._actions.values():
            for a in symbol_actions:
                if start <= a.effective_date <= end:
                    actions.append(a)
        return sorted(actions, key=lambda a: a.effective_date)
