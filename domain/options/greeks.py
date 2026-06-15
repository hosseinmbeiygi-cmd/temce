from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Greeks:
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    speed: float = 0.0
    charm: float = 0.0
    vanna: float = 0.0
    vomma: float = 0.0
