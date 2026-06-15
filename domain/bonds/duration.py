from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DurationMetrics:
    macaulay_duration: float = 0.0
    modified_duration: float = 0.0
    convexity: float = 0.0
    yield_to_maturity: float = 0.0
    current_yield: float = 0.0
