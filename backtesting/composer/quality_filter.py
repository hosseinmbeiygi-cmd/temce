"""Quality Filter: 6-stage filter applied AFTER backtesting to keep only high-quality strategies."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class FilterThresholds:
    min_return_pct: float = 5.0
    max_drawdown_pct: float = 25.0
    min_sharpe: float = 0.5
    min_win_rate: float = 40.0
    min_trades: int = 5
    min_profit_factor: float = 1.2


DEFAULT_THRESHOLDS = FilterThresholds()


class QualityFilter:
    """6-stage quality filter for backtest results."""

    def __init__(self, thresholds: FilterThresholds | None = None) -> None:
        self.thresholds = thresholds or DEFAULT_THRESHOLDS
        self.stats = {"total": 0, "passed": 0, "failed_stage": [0] * 6}

    def should_keep(self, metrics: dict[str, Any]) -> tuple[bool, str]:
        """Check if metrics pass all 6 stages.

        Returns (should_keep, failure_reason).
        """
        self.stats["total"] += 1

        # Stage 1: Minimum return
        if metrics.get("total_return_pct", 0) < self.thresholds.min_return_pct:
            self.stats["failed_stage"][0] += 1
            return False, f"Stage 1: Return {metrics.get('total_return_pct', 0):.1f}% < {self.thresholds.min_return_pct}%"

        # Stage 2: Maximum drawdown
        if metrics.get("max_drawdown_pct", 100) > self.thresholds.max_drawdown_pct:
            self.stats["failed_stage"][1] += 1
            return False, f"Stage 2: Drawdown {metrics.get('max_drawdown_pct', 0):.1f}% > {self.thresholds.max_drawdown_pct}%"

        # Stage 3: Minimum Sharpe ratio
        if metrics.get("sharpe_ratio", 0) < self.thresholds.min_sharpe:
            self.stats["failed_stage"][2] += 1
            return False, f"Stage 3: Sharpe {metrics.get('sharpe_ratio', 0):.2f} < {self.thresholds.min_sharpe}"

        # Stage 4: Minimum win rate
        if metrics.get("win_rate", 0) < self.thresholds.min_win_rate:
            self.stats["failed_stage"][3] += 1
            return False, f"Stage 4: Win rate {metrics.get('win_rate', 0):.1f}% < {self.thresholds.min_win_rate}%"

        # Stage 5: Minimum trades
        if metrics.get("total_trades", 0) < self.thresholds.min_trades:
            self.stats["failed_stage"][4] += 1
            return False, f"Stage 5: Trades {metrics.get('total_trades', 0)} < {self.thresholds.min_trades}"

        # Stage 6: Minimum profit factor
        if metrics.get("profit_factor", 0) < self.thresholds.min_profit_factor:
            self.stats["failed_stage"][5] += 1
            return False, f"Stage 6: Profit factor {metrics.get('profit_factor', 0):.2f} < {self.thresholds.min_profit_factor}"

        self.stats["passed"] += 1
        return True, ""

    def compute_score(self, metrics: dict[str, Any]) -> float:
        """Compute weighted combined score for ranking."""
        return (
            metrics.get("sharpe_ratio", 0) * 0.25 +
            metrics.get("sortino_ratio", 0) * 0.15 +
            metrics.get("calmar_ratio", 0) * 0.10 +
            metrics.get("total_return_pct", 0) * 0.002 +
            metrics.get("profit_factor", 0) * 0.15 +
            metrics.get("win_rate", 0) * 0.005 -
            metrics.get("max_drawdown_pct", 0) * 0.01
        )

    def get_stats(self) -> dict[str, Any]:
        total = self.stats["total"]
        passed = self.stats["passed"]
        return {
            "total": total,
            "passed": passed,
            "pass_rate": round(passed / total * 100, 1) if total > 0 else 0,
            "failed_by_stage": {
                "stage1_return": self.stats["failed_stage"][0],
                "stage2_drawdown": self.stats["failed_stage"][1],
                "stage3_sharpe": self.stats["failed_stage"][2],
                "stage4_winrate": self.stats["failed_stage"][3],
                "stage5_trades": self.stats["failed_stage"][4],
                "stage6_pf": self.stats["failed_stage"][5],
            },
        }

    def reset_stats(self) -> None:
        self.stats = {"total": 0, "passed": 0, "failed_stage": [0] * 6}
