"""Hard risk limits (roadmap v1:112).

Daily and portfolio exposure limits enforced by simulator.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskLimits:
    max_daily_loss_pct: float = 3.0  # stop trading if daily loss exceeds 3%
    max_portfolio_exposure_pct: float = 10.0  # max at-risk vs NAV
    max_single_position_pct: float = 25.0  # no single name >25% NAV

    def check_daily_loss(self, nav_start_day: float, nav_now: float) -> bool:
        """Return True if trading should be halted."""
        if nav_start_day <= 0:
            return False
        loss_pct = (nav_start_day - nav_now) / nav_start_day * 100
        return loss_pct >= self.max_daily_loss_pct

    def check_exposure(self, position_value: float, nav: float) -> bool:
        """Return True if position would breach exposure limit."""
        if nav <= 0:
            return True
        return (position_value / nav * 100) > self.max_single_position_pct

    def position_cap(self, nav: float) -> float:
        return nav * self.max_single_position_pct / 100.0
