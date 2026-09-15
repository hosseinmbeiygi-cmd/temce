"""Regime-Aware Strategy Selection.

Selects optimal strategies based on current market regime:
- Trending: momentum/breakout strategies
- Mean-reverting: RSI reversion, mean reversion
- Panic: defensive, reduce exposure
- Low liquidity: avoid or reduce position sizes
- Normal: balanced approach

This prevents applying the wrong strategy to the wrong market condition.
"""

from __future__ import annotations

from typing import Any

from backtesting.regime.regime_detector import MarketRegime, RegimeDetector
from core.logging import get_logger

logger = get_logger(__name__)


# Strategy preferences by regime
REGIME_STRATEGY_MAP: dict[str, list[dict[str, Any]]] = {
    MarketRegime.TRENDING: [
        {"strategy": "momentum", "weight": 0.3, "reason": "Momentum excels in trending markets"},
        {"strategy": "breakout", "weight": 0.25, "reason": "Breakouts follow trends"},
        {"strategy": "moving_average_cross", "weight": 0.2, "reason": "MA crossover captures trends"},
        {"strategy": "half_trend", "weight": 0.15, "reason": "Trend following indicator"},
        {"strategy": "volatility_breakout", "weight": 0.1, "reason": "Volatility expansion in trends"},
    ],
    MarketRegime.MEAN_REVERTING: [
        {"strategy": "mean_reversion", "weight": 0.3, "reason": "Core mean reversion strategy"},
        {"strategy": "rsi_reversion", "weight": 0.3, "reason": "RSI oversold/overbought works in range"},
        {"strategy": "squeeze_momentum", "weight": 0.2, "reason": "Squeeze releases in range-bound"},
        {"strategy": "support_resistance", "weight": 0.2, "reason": "S/R levels respected in range"},
    ],
    MarketRegime.PANIC: [
        {"strategy": "mean_reversion", "weight": 0.2, "reason": "Oversold bounces in panic"},
        {"strategy": "rsi_reversion", "weight": 0.2, "reason": "Extreme RSI in panic"},
    ],
    MarketRegime.LOW_LIQUIDITY: [
        {"strategy": "mean_reversion", "weight": 0.3, "reason": "Low volume mean reversion"},
        {"strategy": "rsi_reversion", "weight": 0.3, "reason": "RSI works in low volume"},
    ],
    MarketRegime.QUEUE_LOCK: [],  # No strategy — avoid trading
    MarketRegime.NORMAL: [
        {"strategy": "momentum", "weight": 0.2, "reason": "Balanced momentum"},
        {"strategy": "mean_reversion", "weight": 0.2, "reason": "Balanced mean reversion"},
        {"strategy": "rsi_reversion", "weight": 0.15, "reason": "RSI signals"},
        {"strategy": "moving_average_cross", "weight": 0.15, "reason": "MA crossover"},
        {"strategy": "breakout", "weight": 0.15, "reason": "Breakout opportunities"},
        {"strategy": "squeeze_momentum", "weight": 0.15, "reason": "Squeeze signals"},
    ],
}


class RegimeAwareStrategySelector:
    """Selects strategies based on current market regime."""

    def __init__(self, detector: RegimeDetector | None = None) -> None:
        self.detector = detector or RegimeDetector(mode="adaptive")
        self._regime_performance: dict[str, dict[str, float]] = {}

    def update(self, market_state: dict[str, Any]) -> str:
        """Update with new market data and return current regime."""
        return self.detector.update(market_state)

    def select_strategies(
        self,
        regime: str | None = None,
        min_weight: float = 0.05,
        max_strategies: int = 5,
    ) -> list[dict[str, Any]]:
        """Select optimal strategies for current regime.

        Args:
            regime: Override regime (uses detected if None)
            min_weight: Minimum weight threshold
            max_strategies: Maximum number of strategies to return

        Returns:
            List of strategy recommendations with weights and reasons
        """
        current_regime = regime or self.detector.current_regime
        strategies = REGIME_STRATEGY_MAP.get(current_regime, [])

        # Filter by minimum weight
        filtered = [s for s in strategies if s["weight"] >= min_weight]

        # Sort by weight (descending)
        filtered.sort(key=lambda s: s["weight"], reverse=True)

        # Limit to max_strategies
        return filtered[:max_strategies]

    def get_position_sizing_multiplier(self, regime: str | None = None) -> float:
        """Get position sizing multiplier based on regime.

        Returns:
            Multiplier (0.0 to 1.0) to apply to position sizes
        """
        current_regime = regime or self.detector.current_regime

        multipliers = {
            MarketRegime.NORMAL: 1.0,
            MarketRegime.TRENDING: 1.2,  # Increase in trends
            MarketRegime.MEAN_REVERTING: 0.8,  # Reduce in range
            MarketRegime.PANIC: 0.3,  # Heavy reduction in panic
            MarketRegime.LOW_LIQUIDITY: 0.5,  # Reduce in low volume
            MarketRegime.QUEUE_LOCK: 0.0,  # No trading
        }

        return multipliers.get(current_regime, 1.0)

    def should_trade(self, regime: str | None = None) -> tuple[bool, str]:
        """Determine if we should trade in current regime.

        Returns:
            (should_trade, reason)
        """
        current_regime = regime or self.detector.current_regime

        if current_regime == MarketRegime.QUEUE_LOCK:
            return False, "Queue lock detected — no trading recommended"
        if current_regime == MarketRegime.PANIC:
            return True, "Panic regime — trade with extreme caution and reduced size"
        if current_regime == MarketRegime.LOW_LIQUIDITY:
            return True, "Low liquidity — reduce position sizes"

        return True, f"Regime {current_regime} — normal trading"

    def get_regime_report(self) -> dict[str, Any]:
        """Get comprehensive regime analysis report."""
        regime = self.detector.current_regime
        strength = self.detector.regime_strength
        transition_matrix = self.detector.get_transition_matrix()
        features = self.detector.get_features()
        strategies = self.select_strategies()
        sizing = self.get_position_sizing_multiplier()
        should_trade, reason = self.should_trade()

        return {
            "current_regime": regime,
            "regime_strength": round(strength, 3),
            "should_trade": should_trade,
            "trade_reason": reason,
            "position_sizing_multiplier": sizing,
            "recommended_strategies": strategies,
            "regime_features": features,
            "transition_matrix": transition_matrix,
            "regime_history": list(self.detector._regime_history)[-20:],
        }
