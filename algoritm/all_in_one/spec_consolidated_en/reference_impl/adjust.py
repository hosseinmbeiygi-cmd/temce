"""Backward price adjustment for corporate actions (formulas from SPEC_VALUATION section 1, marked [VERIFY] there).

adjusted_close[t] = raw_close[t] * prod(f_j for events with ex_date > t)
Reference price P for an event = last raw close strictly before ex_date.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import pandas as pd


@dataclass(frozen=True)
class Event:
    ex_date: date
    kind: str                       # bonus | cash_dividend | rights | split
    g: float | None = None       # bonus: new shares per old; rights: new shares per old
    dividend: float | None = None
    subscription_price: float | None = None
    split_ratio: float | None = None   # 1 old share -> r new shares


def event_factor(ev: Event, ref_price: float) -> float:
    if ev.kind == "bonus":
        return 1.0 / (1.0 + ev.g)
    if ev.kind == "cash_dividend":
        return (ref_price - ev.dividend) / ref_price
    if ev.kind == "rights":
        terp = (ref_price + ev.g * ev.subscription_price) / (1.0 + ev.g)
        return terp / ref_price
    if ev.kind == "split":
        return 1.0 / ev.split_ratio
    raise ValueError(ev.kind)


def adjusted_close(raw_close: pd.Series, events: Sequence[Event]) -> pd.Series:
    """raw_close indexed by date (sorted). Returns adjusted series."""
    raw = raw_close.sort_index()
    f = pd.Series(1.0, index=raw.index)
    for ev in sorted(events, key=lambda e: e.ex_date):
        prior = raw[raw.index < ev.ex_date]
        if prior.empty:
            continue
        fac = event_factor(ev, float(prior.iloc[-1]))
        f[f.index < ev.ex_date] *= fac
    return raw * f
