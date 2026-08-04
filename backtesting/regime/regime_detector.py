from __future__ import annotations

from collections import deque
from enum import StrEnum
from typing import Any

import numpy as np

from backtesting.regime.regime_features import MicrostructureFeatures
from core.logging import get_logger

logger = get_logger(__name__)


class MarketRegime(StrEnum):
    NORMAL = "normal"
    TRENDING = "trend"
    PANIC = "panic"
    LOW_LIQUIDITY = "low_liquidity"
    QUEUE_LOCK = "queue_lock"
    MEAN_REVERTING = "mean_reverting"


class RegimeDetector:
    """Detects market regimes from microstructure features.

    Supports two modes:
    - rule_based: Simple threshold-based classification
    - threshold_adaptive: Uses rolling statistics for adaptive thresholds
    """

    def __init__(self, mode: str = "rule_based", smoothing: float = 0.7) -> None:
        self.mode = mode
        self.smoothing = smoothing  # Regime memory smoothing factor
        self.features = MicrostructureFeatures(window=50)
        self._regime_history: deque[str] = deque(maxlen=100)
        self._current_regime: str = MarketRegime.NORMAL
        self._regime_features: dict[str, float] = {}
        self._last_features: dict[str, float] = {}

        # Adaptive thresholds (updated from data)
        self._vol_threshold: float = 2.0
        self._imbalance_threshold: float = 0.7
        self._spread_threshold: float = 1.5
        self._feature_history: dict[str, deque[float]] = {
            "realized_vol": deque(maxlen=500),
            "spread": deque(maxlen=500),
            "abs_imbalance": deque(maxlen=500),
        }

    def update(self, market_state: dict[str, Any]) -> str:
        """Update with new market state and return detected regime."""
        features = self.features.update(market_state)
        self._last_features = features

        regime = self._detect_rule_based(features) if self.mode == "rule_based" else self._detect_adaptive(features)

        # Smooth regime transitions
        if regime != self._current_regime:
            self._regime_features = features
        self._current_regime = self._smooth_regime(regime)
        self._regime_history.append(self._current_regime)

        return self._current_regime

    def _detect_rule_based(self, features: dict[str, float]) -> str:
        vol = features.get("realized_vol", 0)
        imbalance = features.get("abs_imbalance", 0)
        spread = features.get("spread", 0)
        trend = features.get("trend_strength", 0)
        avg_spread = float(np.mean(list(self._feature_history["spread"]))) if self._feature_history["spread"] else spread

        # Panic: High volatility
        if vol > self._vol_threshold * max(np.mean(list(self._feature_history["realized_vol"])) + 0.001, 0.001):
            return MarketRegime.PANIC

        # Queue lock: Extreme imbalance
        if imbalance > self._imbalance_threshold:
            return MarketRegime.QUEUE_LOCK

        # Low liquidity: Wide spread
        if avg_spread > 0 and spread > avg_spread * self._spread_threshold:
            return MarketRegime.LOW_LIQUIDITY

        # Trending: Strong trend
        if trend > 0.7:
            return MarketRegime.TRENDING

        # Mean reverting: Low trend, stable vol
        if trend < 0.2 and vol < 1.0:
            return MarketRegime.MEAN_REVERTING

        return MarketRegime.NORMAL

    def _detect_adaptive(self, features: dict[str, float]) -> str:
        vol = features.get("realized_vol", 0)
        imbalance = features.get("abs_imbalance", 0)
        spread = features.get("spread", 0)
        trend = features.get("trend_strength", 0)

        # Update rolling feature history
        self._feature_history["realized_vol"].append(vol)
        self._feature_history["spread"].append(spread)
        self._feature_history["abs_imbalance"].append(imbalance)

        # Compute adaptive thresholds from rolling stats
        if len(self._feature_history["realized_vol"]) >= 20:
            vol_mean = float(np.mean(list(self._feature_history["realized_vol"])))
            vol_std = max(float(np.std(list(self._feature_history["realized_vol"]))), 0.001)
            spread_mean = float(np.mean(list(self._feature_history["spread"]))) + 0.001
            imb_mean = float(np.mean(list(self._feature_history["abs_imbalance"]))) + 0.001

            # Adaptive thresholds
            adaptive_vol_threshold = vol_mean + 2.5 * vol_std
            adaptive_spread_threshold = spread_mean * 2.0
            adaptive_imb_threshold = min(0.9, imb_mean * 2.0)

            if vol > adaptive_vol_threshold and vol > vol_mean * 2:
                return MarketRegime.PANIC
            if imbalance > adaptive_imb_threshold:
                return MarketRegime.QUEUE_LOCK
            if spread > adaptive_spread_threshold:
                return MarketRegime.LOW_LIQUIDITY
            if trend > 0.7:
                return MarketRegime.TRENDING
            if trend < 0.2 and vol < vol_mean:
                return MarketRegime.MEAN_REVERTING

        return MarketRegime.NORMAL

    def _smooth_regime(self, new_regime: str) -> str:
        """Smooth regime transitions to avoid flickering."""
        if not self._regime_history:
            return new_regime

        # Only change regime if the last N+1 detections agree
        recent = list(self._regime_history)[-3:]
        if recent and all(r == new_regime for r in recent):
            return new_regime

        # For extreme regimes, switch faster
        if new_regime in (MarketRegime.PANIC, MarketRegime.QUEUE_LOCK):
            recent_2 = list(self._regime_history)[-1:]
            if recent_2 and recent_2[0] == new_regime:
                return new_regime
            return new_regime  # Allow immediate switch for safety-critical regimes

        return self._current_regime

    @property
    def current_regime(self) -> str:
        return self._current_regime

    @property
    def regime_strength(self) -> float:
        """How confident we are in the current regime (0-1)."""
        if not self._regime_history:
            return 0.5
        recent = list(self._regime_history)[-10:]
        count = sum(1 for r in recent if r == self._current_regime)
        return count / max(len(recent), 1)

    def get_transition_matrix(self) -> dict[str, dict[str, float]]:
        """Get the empirical regime transition matrix from history."""
        if len(self._regime_history) < 2:
            return {}
        transitions: dict[str, dict[str, int]] = {}
        for i in range(1, len(self._regime_history)):
            from_r = self._regime_history[i - 1]
            to_r = self._regime_history[i]
            if from_r not in transitions:
                transitions[from_r] = {}
            transitions[from_r][to_r] = transitions[from_r].get(to_r, 0) + 1

        matrix: dict[str, dict[str, float]] = {}
        for from_r, targets in transitions.items():
            total = sum(targets.values())
            matrix[from_r] = {t: c / total for t, c in targets.items()}
        return matrix

    def get_features(self) -> dict[str, float]:
        return dict(self._last_features)

    def reset(self) -> None:
        self.features.reset()
        self._regime_history.clear()
        self._current_regime = MarketRegime.NORMAL
        self._regime_features = {}
        self._last_features = {}
        for key in self._feature_history:
            self._feature_history[key].clear()
