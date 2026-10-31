"""FIN-03/FIN-08: the study and the live strategy score the same rule.

Before this fix ``backtest.run_backtest`` measured days with ``bubble > 8``
while the live DCA strategy buys when ``bubble < trigger`` — the backtest
described the opposite population. The predicate now lives in
``entry_rules.dca_entry_signal`` and both sides import it.

FIN-08: the DCA simulation filled at the **signal day's close**; a close is
only known after the session, so the fill moves to the next bar's close. A
signal on the last bar cannot be executed and must not be counted.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.gold_desk import backtest as backtest_module
from src.gold_desk.backtest import run_backtest
from src.gold_desk.backtest_runner import _simulate_dca
from src.gold_desk.entry_rules import dca_entry_signal


def _closes(n: int = 90) -> list[tuple[date, float]]:
    start = date(2025, 1, 1)
    return [(start + timedelta(days=i), 100.0 * (1.001**i)) for i in range(n)]


# ── shared predicate ───────────────────────────────────────────────────────


def test_entry_signal_is_below_strict() -> None:
    assert dca_entry_signal(4.9, 5.0) is True
    assert dca_entry_signal(5.0, 5.0) is False, "the live rule is strict <"
    assert dca_entry_signal(5.1, 5.0) is False
    assert dca_entry_signal(None, 5.0) is False
    assert dca_entry_signal(float("nan"), 5.0) is False


@pytest.mark.asyncio
async def test_backtest_scores_the_days_the_strategy_would_buy(monkeypatch) -> None:
    rows = [
        ("1405-01-01", -2.0, 3.0),   # signal
        ("1405-01-02", 9.0, -4.0),   # NOT a signal (old predicate picked this)
        ("1405-01-03", 4.0, 1.0),    # signal
        ("1405-01-04", 6.0, 2.0),    # NOT a signal
    ]

    async def fake_rows(_session, _symbol, _days):
        return rows

    monkeypatch.setattr(backtest_module, "_daily_bubble_pct", fake_rows)

    result = await run_backtest(session=None, bubble_threshold=5.0)  # type: ignore[arg-type]

    assert result.total_days == 4
    assert result.score_above_threshold_days == 2
    # Only the two signal days' forward returns are averaged: (3 + 1) / 2.
    assert result.forward_return_30d_avg == pytest.approx(2.0)


# ── next-bar execution ────────────────────────────────────────────────────


def test_dca_fills_on_the_next_bar_not_the_signal_close(monkeypatch) -> None:
    import numpy as np

    from src.gold_desk import backtest_runner

    closes = _closes(30)
    # Bubble is below the trigger on every bar: the first bar signals.
    monkeypatch.setattr(
        backtest_runner.indicators,
        "bubble_pct",
        lambda prices, window: np.zeros(len(prices)),
    )

    trades = _simulate_dca(closes, [1.0, 0.0, 0.0], bubble_trigger=5.0)

    assert len(trades) == 1
    trade = trades[0]
    assert trade.date == closes[1][0], "fill belongs to the bar after the signal"
    assert trade.price == pytest.approx(closes[1][1])


def test_a_signal_on_the_last_bar_is_not_executed(monkeypatch) -> None:
    import numpy as np

    from src.gold_desk import backtest_runner

    closes = _closes(30)

    def late_signal(prices, window):
        values = np.full(len(prices), 20.0)  # above the trigger everywhere…
        values[-1] = 1.0                     # …except the very last bar
        return values

    monkeypatch.setattr(backtest_runner.indicators, "bubble_pct", late_signal)

    trades = _simulate_dca(closes, [1.0, 0.0, 0.0], bubble_trigger=5.0)

    assert trades == [], "last-bar signals have no next bar to fill on"
