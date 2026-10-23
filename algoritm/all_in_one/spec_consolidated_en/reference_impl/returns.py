"""Nominal / real / USD reporting helpers. Cash-flow convention: investor outflow < 0, inflow > 0."""
from __future__ import annotations
from datetime import date
from typing import Mapping, Sequence, Tuple
from scipy.optimize import brentq

Flow = Tuple[date, float]


def nominal_pnl(ending_value: float, contributions: float, withdrawals: float) -> float:
    """P&L = ending value + money already taken out - money put in (withdrawals ADD to P&L)."""
    return ending_value + withdrawals - contributions


def xirr(flows: Sequence[Flow], lo: float = -0.99, hi: float = 100.0) -> float:
    t0 = min(d for d, _ in flows)
    def f(r):
        return sum(cf / (1.0 + r) ** ((d - t0).days / 365.0) for d, cf in flows)
    return brentq(f, lo, hi)


def deflate(flows: Sequence[Flow], cpi: Mapping[date, float], base: date) -> list:
    """Express flows in base-date money: cf * CPI(base) / CPI(d). The caller chooses the CPI vintage."""
    return [(d, cf * cpi[base] / cpi[d]) for d, cf in flows]


def to_usd(flows: Sequence[Flow], fx_rial_per_usd: Mapping[date, float]) -> list:
    return [(d, cf / fx_rial_per_usd[d]) for d, cf in flows]
