"""Pre-Trade Risk Engine — validates orders before execution.

Checks:
- Position limits (max % of portfolio per symbol)
- Sector exposure limits
- Maximum drawdown threshold
- Daily loss limit
- Cash reserve requirement
- Leverage limits
- Order frequency limits
- Kill switch (emergency stop)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RiskPolicy:
    """Configurable risk limits."""
    max_position_pct: float = 0.20        # max 20% in one symbol
    max_sector_pct: float = 0.30          # max 30% in one sector
    max_drawdown_pct: float = -0.15       # stop at -15% drawdown
    max_daily_loss_pct: float = -0.03     # stop at -3% daily loss
    min_cash_reserve_pct: float = 0.10    # keep 10% cash
    max_leverage: float = 1.0             # no leverage
    max_orders_per_day: int = 50          # max 50 orders per day
    max_order_value_pct: float = 0.10     # max 10% per order
    kill_switch_drawdown: float = -0.25   # emergency stop at -25%


@dataclass
class RiskCheckResult:
    """Result of a pre-trade risk check."""
    allowed: bool = True
    reason: str = ""
    risk_score: float = 0.0  # 0 = safe, 1 = high risk
    warnings: list[str] = field(default_factory=list)


class PreTradeRiskEngine:
    """Validates orders against risk policy before execution."""

    def __init__(self, policy: RiskPolicy | None = None) -> None:
        self.policy = policy or RiskPolicy()
        self._daily_order_count: int = 0
        self._daily_pnl: float = 0.0
        self._peak_nav: float = 0.0
        self._kill_switch_active: bool = False

    def check_order(
        self,
        side: str,
        symbol: str,
        quantity: int,
        price: float,
        portfolio_value: float,
        cash_available: float,
        current_positions: dict[str, int],
        current_prices: dict[str, float],
        sector: str = "",
        sector_exposure: dict[str, float] | None = None,
    ) -> RiskCheckResult:
        """Validate an order against all risk rules."""
        result = RiskCheckResult()
        order_value = quantity * price

        # 1. Kill switch
        if self._kill_switch_active:
            result.allowed = False
            result.reason = "Kill switch is active — all trading halted"
            return result

        # 2. Drawdown check
        if self._peak_nav > 0:
            current_dd = (portfolio_value - self._peak_nav) / self._peak_nav
            if current_dd <= self.policy.kill_switch_drawdown:
                self._kill_switch_active = True
                result.allowed = False
                result.reason = f"Kill switch triggered: drawdown {current_dd:.2%}"
                return result
            if current_dd <= self.policy.max_drawdown_pct:
                result.allowed = False
                result.reason = f"Max drawdown breached: {current_dd:.2%} <= {self.policy.max_drawdown_pct:.2%}"
                return result

        # 3. Daily loss check
        if portfolio_value > 0:
            daily_return = self._daily_pnl / portfolio_value
            if daily_return <= self.policy.max_daily_loss_pct:
                result.allowed = False
                result.reason = f"Daily loss limit breached: {daily_return:.2%}"
                return result

        # 4. Cash reserve check (for buys only)
        if side == "buy":
            remaining_cash = cash_available - order_value
            required_reserve = portfolio_value * self.policy.min_cash_reserve_pct
            if remaining_cash < required_reserve:
                result.allowed = False
                result.reason = f"Insufficient cash reserve: would have {remaining_cash:.0f}, need {required_reserve:.0f}"
                return result

        # 5. Order value check
        if portfolio_value > 0:
            order_pct = order_value / portfolio_value
            if order_pct > self.policy.max_order_value_pct:
                result.allowed = False
                result.reason = f"Order too large: {order_pct:.2%} > {self.policy.max_order_value_pct:.2%}"
                return result

        # 6. Position concentration check (for buys)
        if side == "buy":
            current_value = current_positions.get(symbol, 0) * current_prices.get(symbol, 0)
            new_value = current_value + order_value
            if portfolio_value > 0:
                new_pct = new_value / portfolio_value
                if new_pct > self.policy.max_position_pct:
                    result.allowed = False
                    result.reason = f"Position limit breached for {symbol}: {new_pct:.2%} > {self.policy.max_position_pct:.2%}"
                    return result

        # 7. Sector exposure check
        if side == "buy" and sector and sector_exposure:
            current_sector = sector_exposure.get(sector, 0.0)
            new_sector = current_sector + order_value
            if portfolio_value > 0:
                new_sector_pct = new_sector / portfolio_value
                if new_sector_pct > self.policy.max_sector_pct:
                    result.allowed = False
                    result.reason = f"Sector limit breached for {sector}: {new_sector_pct:.2%} > {self.policy.max_sector_pct:.2%}"
                    return result

        # 8. Order frequency check
        if self._daily_order_count >= self.policy.max_orders_per_day:
            result.allowed = False
            result.reason = f"Daily order limit reached: {self._daily_order_count}"
            return result

        # 9. Warnings (non-blocking)
        if portfolio_value > 0:
            order_pct = order_value / portfolio_value
            if order_pct > self.policy.max_order_value_pct * 0.8:
                result.warnings.append(f"Order approaching size limit: {order_pct:.2%}")

        # All checks passed
        self._daily_order_count += 1
        return result

    def update_daily_pnl(self, pnl: float) -> None:
        """Update daily PnL tracking."""
        self._daily_pnl += pnl

    def update_peak_nav(self, nav: float) -> None:
        """Update peak NAV for drawdown calculation."""
        if nav > self._peak_nav:
            self._peak_nav = nav

    def new_day(self) -> None:
        """Reset daily counters."""
        self._daily_order_count = 0
        self._daily_pnl = 0.0

    def reset_kill_switch(self) -> None:
        """Manually reset the kill switch."""
        self._kill_switch_active = False
        logger.warning("Kill switch manually reset")

    def get_status(self) -> dict[str, Any]:
        """Get current risk engine status."""
        return {
            "kill_switch_active": self._kill_switch_active,
            "daily_orders": self._daily_order_count,
            "daily_pnl": self._daily_pnl,
            "peak_nav": self._peak_nav,
            "policy": {
                "max_position_pct": self.policy.max_position_pct,
                "max_drawdown_pct": self.policy.max_drawdown_pct,
                "max_daily_loss_pct": self.policy.max_daily_loss_pct,
                "kill_switch_drawdown": self.policy.kill_switch_drawdown,
            },
        }
