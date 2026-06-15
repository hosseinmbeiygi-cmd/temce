from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

PRICING_MODEL_BLACK_SCHOLES = "black_scholes"
PRICING_MODEL_BINOMIAL = "binomial"
PRICING_MODEL_MONTE_CARLO = "monte_carlo"
PRICING_MODEL_WHITE = "whale"


@dataclass
class OptionPrice:
    model: str = ""
    price: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    implied_vol: float = 0.0
    intrinsic_value: float = 0.0
    time_value: float = 0.0
    parameters: dict[str, Any] = field(default_factory=dict)
