"""Stress scenarios (roadmap v2:51 + v2:135-136).

Inject 3-5x normal slippage on N% of trades and flash-crash / queue simulation.
"""

from __future__ import annotations

import random


def apply_stress_slippage(
    bars: list[dict],
    stress_pct: float = 10.0,
    multiplier: float = 4.0,
    seed: int = 42,
) -> list[dict]:
    """Mark N% of bars as stressed so Broker multiplies slippage 3-5x.

    Callers pass the returned bars into simulator with stress_multiplier.
    The simulator will apply multiplier only on marked bars.
    """
    rnd = random.Random(seed)
    out = []
    for bar in bars:
        stressed = rnd.random() * 100 < stress_pct
        nb = dict(bar)
        if stressed:
            nb["stress_multiplier"] = multiplier
            nb["is_stressed"] = True
        out.append(nb)
    return out


def flash_crash_bar(bar: dict, crash_pct: float = 0.15) -> dict:
    """Create a flash-crash variant of a bar for scenario testing."""
    nb = dict(bar)
    nb["close"] = float(bar.get("close", 0)) * (1 - crash_pct)
    nb["low"] = min(float(bar.get("low", bar.get("close", 0))), nb["close"])
    nb["is_flash_crash"] = True
    return nb
