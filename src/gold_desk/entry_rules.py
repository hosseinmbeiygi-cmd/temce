"""Entry predicates shared by the live strategy and its backtest (audit FIN-03).

The live DCA strategy and the historical study used **opposite** bubble
predicates: the strategy buys when the technical bubble is *below* its trigger
(``backtest_runner._simulate_dca``), while ``backtest.run_backtest`` measured
``bubble > 8`` days. A backtest of the strategy must score the same days the
strategy would actually enter, so the predicate lives here once and both
sides import it.
"""

from __future__ import annotations

import math


def dca_entry_signal(bubble_pct: float | None, threshold: float) -> bool:
    """Live tranche-1 rule: enter when the technical bubble is below *threshold*.

    ``None``/NaN is not a signal: a missing bubble is unknown data, not a
    bargain. The comparison is strict (``<``) to match the live simulation
    exactly — a day whose bubble equals the trigger does not buy.
    """
    if bubble_pct is None:
        return False
    try:
        value = float(bubble_pct)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(value):
        return False
    return value < threshold


__all__ = ["dca_entry_signal"]
