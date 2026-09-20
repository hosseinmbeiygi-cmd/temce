"""Pure-math tests for corporate-action adjustment factors (audit §2 fix).

No DB needed — everything goes through ``compute_cumulative_factors``
(the single source of truth shared by the backfill script and any
runtime recomputation). Real-world shape: a 100% capital increase
doubles shares so pre-event prices must halve; DPS reduces pre-event
prices by the yield; multiple events compound walking backwards.
"""

from datetime import date

import pytest

from services.corporate_action_service import (
    compute_cumulative_factors,
    normalize_action_type,
)

D = date


def _run(actions, trade_dates, closes=None):
    return compute_cumulative_factors(actions, trade_dates, closes or {})


class TestSingleEvent:
    def test_capital_increase_100pct_halves_pre_event_prices(self):
        # 100% increase (ratio=1.0) → factor 1/2 for all dates before ex-date
        factors = _run(
            [{"ex_date": D(2026, 3, 20), "action_type": "capital_increase", "ratio": 1.0, "dps": 0}],
            [D(2026, 3, 18), D(2026, 3, 19), D(2026, 3, 20), D(2026, 3, 21)],
        )
        assert factors[D(2026, 3, 18)] == pytest.approx(0.5)
        assert factors[D(2026, 3, 19)] == pytest.approx(0.5)
        # ex-date itself and after stay raw
        assert factors[D(2026, 3, 20)] == pytest.approx(1.0)
        assert factors[D(2026, 3, 21)] == pytest.approx(1.0)

    def test_dividend_factor_uses_close_at_ex(self):
        # close=2000, DPS=200 → (2000-200)/2000 = 0.9
        factors = _run(
            [{"ex_date": D(2026, 3, 20), "action_type": "dividend", "ratio": 0, "dps": 200}],
            [D(2026, 3, 19), D(2026, 3, 20)],
            closes={D(2026, 3, 20): 2000.0},
        )
        assert factors[D(2026, 3, 19)] == pytest.approx(0.9)
        assert factors[D(2026, 3, 20)] == pytest.approx(1.0)

    def test_no_events_all_ones(self):
        factors = _run([], [D(2026, 1, 1), D(2026, 1, 2)])
        assert all(f == 1.0 for f in factors.values())


class TestChained:
    def test_two_events_compound_backwards(self):
        # ex 06-01 ratio=1.0 (×0.5); ex 09-01 ratio=3.0 (×0.25)
        factors = _run(
            [
                {"ex_date": D(2026, 6, 1), "action_type": "capital_increase", "ratio": 1.0, "dps": 0},
                {"ex_date": D(2026, 9, 1), "action_type": "capital_increase", "ratio": 3.0, "dps": 0},
            ],
            [D(2026, 3, 1), D(2026, 7, 1), D(2026, 9, 1)],
        )
        assert factors[D(2026, 7, 1)] == pytest.approx(0.25)   # only 09-01 ahead
        assert factors[D(2026, 3, 1)] == pytest.approx(0.125)  # both ahead: 0.5×0.25
        assert factors[D(2026, 9, 1)] == pytest.approx(1.0)

    def test_bonus_after_window_still_adjusts_inside(self):
        factors = _run(
            [{"ex_date": D(2026, 12, 1), "action_type": "bonus", "ratio": 1.0, "dps": 0}],
            [D(2026, 1, 1)],
        )
        assert factors[D(2026, 1, 1)] == pytest.approx(0.5)


class TestGuards:
    def test_invalid_ratio_raises(self):
        with pytest.raises(ValueError):
            compute_cumulative_factors(
                [{"ex_date": D(2026, 1, 1), "action_type": "capital_increase", "ratio": -1.0, "dps": 0}],
                [D(2025, 12, 1)],
            )

    def test_dividend_without_close_is_noop(self):
        # no close supplied → factor 1 (logged, not raised) — defensive against data holes
        factors = _run(
            [{"ex_date": D(2026, 1, 1), "action_type": "dividend", "ratio": 0, "dps": 500}],
            [D(2025, 12, 31)],
        )
        assert factors[D(2025, 12, 31)] == pytest.approx(1.0)


def test_normalize_action_type_aliases():
    assert normalize_action_type("افزایش سرمایه") == "capital_increase"
    assert normalize_action_type("Bonus") == "bonus"
    assert normalize_action_type("سود نقدی") == "dividend"
