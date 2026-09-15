"""Capacity Analysis — determines how much capital a strategy can handle.

Key questions:
- At what capital level does Sharpe start decaying?
- What is the average participation rate?
- How many days to liquidate a position?
- What is the worst-case exit slippage?
- What is the queue lock risk?
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CapacityResult:
    """Capacity analysis results."""

    max_capital_before_sharpe_decay: float = 0.0
    avg_participation_rate: float = 0.0  # order_size / ADV
    days_to_liquidate_avg: float = 0.0
    days_to_liquidate_worst: float = 0.0
    worst_case_exit_slippage_bps: float = 0.0
    avg_turnover: float = 0.0
    avg_trade_size: float = 0.0
    avg_adv: float = 0.0
    capacity评级: str = "unknown"  # small / medium / large / institutional
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


class CapacityAnalyzer:
    """Analyzes strategy capacity based on liquidity and trade characteristics."""

    def analyze(
        self,
        trades: list[dict[str, Any]],
        daily_volumes: dict[str, float] | None = None,  # date -> ADV
        capital_levels: list[float] | None = None,
        strategy_returns_by_capital: dict[float, list[float]] | None = None,
    ) -> CapacityResult:
        """Run capacity analysis."""
        result = CapacityResult()

        if not trades:
            return result

        # Basic trade statistics
        trade_values = [abs(t.get("price", 0) * t.get("quantity", 0)) for t in trades]
        result.avg_trade_size = float(np.mean(trade_values)) if trade_values else 0.0
        result.avg_turnover = len(trades)

        # ADV and participation rate
        if daily_volumes:
            advs = list(daily_volumes.values())
            result.avg_adv = float(np.mean(advs)) if advs else 0.0
            if result.avg_adv > 0:
                result.avg_participation_rate = result.avg_trade_size / result.avg_adv

        # Days to liquidate (estimate)
        if result.avg_adv > 0:
            avg_position = result.avg_trade_size * 2  # rough estimate
            result.days_to_liquidate_avg = avg_position / result.avg_adv
            result.days_to_liquidate_worst = result.days_to_liquidate_avg * 3  # worst case

        # Sharpe decay analysis
        if strategy_returns_by_capital and capital_levels:
            sharpes = []
            for cap in capital_levels:
                rets = strategy_returns_by_capital.get(cap, [])
                if len(rets) > 1:
                    sharpe = float(np.mean(rets) / np.std(rets, ddof=1) * np.sqrt(252)) if np.std(rets) > 0 else 0
                    sharpes.append((cap, sharpe))

            if len(sharpes) >= 2:
                # Find where Sharpe drops below 80% of peak
                peak_sharpe = max(s for _, s in sharpes)
                threshold = peak_sharpe * 0.8
                for cap, sharpe in sharpes:
                    if sharpe < threshold:
                        result.max_capital_before_sharpe_decay = cap
                        break
                else:
                    result.max_capital_before_sharpe_decay = sharpes[-1][0]

        # Rating
        if result.avg_participation_rate < 0.01:
            result.capacity评级 = "institutional"
        elif result.avg_participation_rate < 0.05:
            result.capacity评级 = "large"
        elif result.avg_participation_rate < 0.15:
            result.capacity评级 = "medium"
        else:
            result.capacity评级 = "small"
            result.warnings.append("High participation rate — strategy may not scale")

        return result
