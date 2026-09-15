from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backtesting.meta_strategy.alpha_switcher import MetaStrategy
from backtesting.regime.adaptive_impact import RegimeAwareExecution


@dataclass
class MetaDecision:
    """Decision from the meta-strategy layer."""

    combined_signal: float = 0.0
    active_alphas: list[str] = field(default_factory=list)
    regime: str = "normal"
    exposure_level: float = 1.0
    execution_style: str = "VWAP"
    should_trade: bool = True
    risk_limit: float = 1.0


class MetaExecutor:
    """Connects regime detection, alpha switching, and execution decisions.

    Flow:
    RegimeDetector → MetaStrategy (alpha selection) → Execution decision
    """

    def __init__(self, meta_strategy: MetaStrategy | None = None) -> None:
        self.meta_strategy = meta_strategy or MetaStrategy()
        self._current_regime: str = "normal"
        self._execution_behavior: dict[str, Any] = {}
        self._decision_history: list[MetaDecision] = []

    def update(self, regime: str, alpha_signals: dict[str, float]) -> MetaDecision:
        """Update with new regime and alpha signals, return execution decision.

        Args:
            regime: Current market regime
            alpha_signals: Dict of {alpha_id: current_signal}

        Returns:
            MetaDecision with combined signal and execution parameters
        """
        self._current_regime = regime
        self.meta_strategy.set_regime(regime)

        for alpha_id, signal in alpha_signals.items():
            self.meta_strategy.update_alpha_signal(alpha_id, signal)

        combined = self.meta_strategy.get_combined_signal()
        active = self.meta_strategy.get_active_alphas()
        exec_behavior = RegimeAwareExecution.get_execution_behavior(regime)

        # Exposure management
        exposure_level = 1.0
        should_trade = True

        if regime in ("panic",):
            exposure_level = 0.0
            should_trade = False
        elif regime == "low_liquidity":
            exposure_level = 0.5
        elif regime == "queue_lock":
            exposure_level = 0.3

        decision = MetaDecision(
            combined_signal=combined,
            active_alphas=active,
            regime=regime,
            exposure_level=exposure_level,
            execution_style=exec_behavior.get("style", "VWAP"),
            should_trade=should_trade,
            risk_limit=exposure_level,
        )

        self._decision_history.append(decision)
        self._execution_behavior = exec_behavior
        return decision

    @property
    def last_decision(self) -> MetaDecision | None:
        return self._decision_history[-1] if self._decision_history else None

    @property
    def execution_style(self) -> str:
        return self._execution_behavior.get("style", "VWAP")

    def reset(self) -> None:
        self.meta_strategy.reset()
        self._decision_history.clear()
        self._current_regime = "normal"
        self._execution_behavior = {}
