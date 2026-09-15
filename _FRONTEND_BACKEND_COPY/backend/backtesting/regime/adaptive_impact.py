from __future__ import annotations

from typing import Any

from backtesting.microstructure.impact_model import ImpactModel


class AdaptiveImpactModel(ImpactModel):
    """Impact model that adjusts its parameters based on market regime.

    In Panic: eta increases (higher impact)
    In Normal: standard parameters
    In Low Liquidity: higher impact, lower alpha
    """

    def __init__(
        self,
        eta: float = 0.1,
        alpha: float = 0.6,
        permanent_impact_pct: float = 0.02,
        use_sqrt_law: bool = True,
    ) -> None:
        super().__init__(eta, alpha, permanent_impact_pct, use_sqrt_law)
        self._current_regime: str = "normal"

    def set_regime(self, regime: str) -> None:
        self._current_regime = regime

    def calculate_impact(self, quantity: int, adv: float, price: float = 1.0) -> float:
        eta_adj, alpha_adj = self._get_regime_params()
        participation = quantity / max(adv, 1)
        impact = eta_adj * participation**alpha_adj if self.use_sqrt_law else eta_adj * participation
        return impact

    def get_execution_price(self, quantity: int, adv: float, price: float, side: str) -> float:
        impact_pct = self.calculate_impact(quantity, adv, price)
        if side == "buy":
            return price * (1.0 + impact_pct)
        return price * (1.0 - impact_pct)

    def _get_regime_params(self) -> tuple[float, float]:
        params = {
            "normal": (self.eta, self.alpha),
            "trend": (self.eta * 1.2, self.alpha * 0.9),
            "panic": (self.eta * 3.0, self.alpha * 1.2),
            "low_liquidity": (self.eta * 2.0, self.alpha * 0.7),
            "queue_lock": (self.eta * 1.5, self.alpha * 1.1),
            "mean_reverting": (self.eta * 0.8, self.alpha),
        }
        return params.get(self._current_regime, (self.eta, self.alpha))


class RegimeAwareExecution:
    """Provides execution behavior recommendations based on market regime."""

    @staticmethod
    def get_execution_behavior(regime: str) -> dict[str, Any]:
        behaviors = {
            "normal": {
                "style": "VWAP",
                "urgency": "normal",
                "participation": 0.1,
                "max_slice": 0.05,
                "description": "Standard VWAP execution",
            },
            "trend": {
                "style": "POV",
                "urgency": "aggressive",
                "participation": 0.2,
                "max_slice": 0.1,
                "description": "Aggressive percentage of volume",
            },
            "panic": {
                "style": "STOP",
                "urgency": "stop",
                "participation": 0.0,
                "max_slice": 0.0,
                "description": "Stop trading immediately",
            },
            "low_liquidity": {
                "style": "TWAP",
                "urgency": "passive",
                "participation": 0.03,
                "max_slice": 0.02,
                "description": "Passive time-weighted average price",
            },
            "queue_lock": {
                "style": "JOIN_QUEUE",
                "urgency": "passive",
                "participation": 0.05,
                "max_slice": 0.03,
                "description": "Join queue with limit orders",
            },
            "mean_reverting": {
                "style": "OPPOSITE",
                "urgency": "moderate",
                "participation": 0.15,
                "max_slice": 0.08,
                "description": "Trade against extreme moves",
            },
        }
        return behaviors.get(regime, behaviors["normal"])
