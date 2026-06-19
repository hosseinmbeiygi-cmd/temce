from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DrawdownControl:
    max_drawdown_pct: float = 15.0
    _peak: float = 0.0
    _current_dd: float = 0.0
    _stopped: bool = False

    def update(self, nav: float) -> None:
        self._peak = max(self._peak, nav)
        if self._peak > 0:
            self._current_dd = (nav - self._peak) / self._peak * 100

    def is_breached(self) -> bool:
        if self._stopped:
            return True
        if self._current_dd <= -self.max_drawdown_pct:
            self._stopped = True
            return True
        return False

    def is_triggered(self, positions: dict[str, int], event: Any) -> bool:
        """Check if drawdown control is breached."""
        return self.is_breached()

    def get_current_drawdown(self) -> float:
        return self._current_dd

    def reset(self) -> None:
        self._peak = 0.0
        self._current_dd = 0.0
        self._stopped = False
