from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ConditionalValueAtRisk:
    confidence: float = 0.95
    horizon_days: int = 1

    def compute(self, returns: list[float]) -> float:
        if len(returns) < 2:
            return 0.0
        arr = np.array(returns)
        var = float(np.percentile(arr, (1 - self.confidence) * 100))
        tail = arr[arr <= var]
        if len(tail) == 0:
            return var
        cvar = float(tail.mean())
        return cvar * np.sqrt(self.horizon_days)
