from __future__ import annotations

from collections import deque


class RegimeMemory:
    """Smooths regime transitions using exponential moving average.

    R_t = lambda * R_{t-1} + (1 - lambda) * R_new

    This prevents regime from changing on every tick and provides
    a stable regime signal for downstream components.
    """

    def __init__(self, smoothing: float = 0.85, memory_size: int = 50) -> None:
        self.smoothing = smoothing
        self._history: deque[str] = deque(maxlen=memory_size)
        self._current: str = "normal"
        self._scores: dict[str, float] = {}

    def update(self, raw_regime: str, features: dict[str, float] | None = None) -> str:
        """Update with a raw regime detection and return the smoothed regime."""
        score = features.get("regime_confidence", 1.0) if features else 1.0
        self._scores[raw_regime] = self._scores.get(raw_regime, 0.0) * self.smoothing + score * (1 - self.smoothing)

        # Find highest scoring regime
        best_regime = max(self._scores, key=self._scores.get) if self._scores else raw_regime
        best_score = self._scores.get(best_regime, 0.0)

        # Only switch if score is significantly higher
        current_score = self._scores.get(self._current, 0.0)
        if best_score > current_score * 1.2:
            self._current = best_regime

        self._history.append(self._current)
        return self._current

    @property
    def current(self) -> str:
        return self._current

    @property
    def stability(self) -> float:
        """How stable the regime has been recently (0-1)."""
        if len(self._history) < 2:
            return 1.0
        recent = list(self._history)[-10:]
        if not recent:
            return 1.0
        dominant = max(set(recent), key=recent.count)
        return recent.count(dominant) / len(recent)

    def get_transition_probability(self, from_regime: str, to_regime: str) -> float:
        """Get the probability of transitioning from one regime to another."""
        if len(self._history) < 2:
            return 0.0
        transitions = 0
        total = 0
        for i in range(1, len(self._history)):
            if self._history[i - 1] == from_regime:
                total += 1
                if self._history[i] == to_regime:
                    transitions += 1
        return transitions / max(total, 1)

    def reset(self) -> None:
        self._history.clear()
        self._current = "normal"
        self._scores.clear()
