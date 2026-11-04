from __future__ import annotations

from datetime import date

import pytest

from scripts.import_corporate_actions import (
    Adjustment,
    _dividend_rows,
    pick_filing,
    synthetic_symbol_id,
)


def _filing(d: str, title: str = "آگهی ثبت افزایش سرمایه"):
    return (date.fromisoformat(d), title, f"http://codal/{d}")


# ── pick_filing ──────────────────────────────────────────────────────────────


def test_pick_filing_returns_none_without_filings():
    assert pick_filing([], set(), date(2026, 9, 12)) is None


def test_pick_filing_prefers_a_filing_after_the_ex_date():
    filings = [_filing("2026-06-01"), _filing("2026-09-20")]
    # 2026-06-01 is closer in days (103) than 2026-09-20 (only 8) — but the
    # later one wins because registration follows the ex-date.
    assert pick_filing(filings, set(), date(2026, 9, 12)) == 1


def test_pick_filing_picks_the_closest_following_filing():
    filings = [_filing("2026-10-30"), _filing("2026-09-20"), _filing("2026-09-15")]
    assert pick_filing(filings, set(), date(2026, 9, 12)) == 2


def test_pick_filing_falls_back_to_a_preceding_filing():
    filings = [_filing("2026-08-01"), _filing("2025-04-01")]
    assert pick_filing(filings, set(), date(2026, 9, 12)) == 0


def test_pick_filing_skips_used_filings():
    filings = [_filing("2026-09-20"), _filing("2026-09-15")]
    assert pick_filing(filings, {1}, date(2026, 9, 12)) == 0


def test_pick_filing_respects_the_window():
    filings = [_filing("2024-01-01")]
    assert pick_filing(filings, set(), date(2026, 9, 12)) is None
    # a wide enough window admits it
    assert pick_filing(filings, set(), date(2026, 9, 12), before_days=1200) == 0


def test_pick_filing_window_is_inclusive_on_both_edges():
    ex = date(2026, 9, 12)
    before, after = _filing("2026-05-15"), _filing("2027-05-10")
    assert (before[0] - ex).days == -120 and (after[0] - ex).days == 240
    # exactly on both edges: admitted
    assert pick_filing([before], set(), ex) == 0
    assert pick_filing([after], set(), ex) == 0
    # one day past each edge: rejected
    assert pick_filing([_filing("2026-05-14")], set(), ex) is None
    assert pick_filing([_filing("2027-05-11")], set(), ex) is None


# ── synthetic_symbol_id ──────────────────────────────────────────────────────


def test_synthetic_symbol_id_is_deterministic_and_in_its_band():
    for sym in ("ومهان", "فولاد", "شساخت", "آ س پ3"):
        first = synthetic_symbol_id(sym)
        assert first == synthetic_symbol_id(sym)
        assert 10**18 <= first < 10**18 + 10**15


def test_synthetic_symbol_ids_do_not_collide():
    symbols = [f"نماد{i}" for i in range(2000)]
    ids = {synthetic_symbol_id(s) for s in symbols}
    assert len(ids) == len(symbols)


# ── _dividend_rows ───────────────────────────────────────────────────────────


def test_dividend_dps_reproduces_the_observed_factor():
    """The service uses (close − dps)/close, so dps must invert f exactly."""
    adj = Adjustment("فولاد", date(2026, 5, 1), 1000.0, 900.0, 0.9)
    rows = _dividend_rows([adj], set(), {"فولاد": 42})
    assert len(rows) == 1
    sid, ex_date, action_type, ratio, dps, source, ref, _notes = rows[0]
    assert (sid, ex_date, action_type) == (42, date(2026, 5, 1), "dividend")
    assert ratio == 0.0 and source == "tsetmc" and ref is None
    close = adj.close
    assert (close - dps) / close == pytest.approx(adj.f, abs=1e-6)


def test_dividend_skips_days_claimed_by_a_matched_filing():
    adj = Adjustment("فولاد", date(2026, 5, 1), 1000.0, 900.0, 0.9)
    pairs = {("فولاد", date(2026, 5, 1))}
    assert _dividend_rows([adj], pairs, {"فولاد": 42}) == []


def test_dividend_skips_symbols_without_a_symbol_id():
    adj = Adjustment("ناشناس", date(2026, 5, 1), 1000.0, 900.0, 0.9)
    assert _dividend_rows([adj], set(), {}) == []


def test_dividend_skips_nonsensical_dps():
    # f >= 1 was filtered upstream in SQL, but guard anyway: dps must be
    # strictly between 0 and the ex-date close.
    flat = Adjustment("فولاد", date(2026, 5, 1), 1000.0, 1000.0, 1.0)
    assert _dividend_rows([flat], set(), {"فولاد": 42}) == []


# ── ratio convention ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("f", "ratio"),
    [
        (2 / 3, 0.5),        # ومهان 2026-09-12, shares ×1.5
        (0.25, 3.0),         # سیدکو 2026-09-01, shares ×4
        (1 / 5.19, 4.19),    # شساخت 2026-09-02
        (0.5, 1.0),          # 100% capital increase from retained earnings
    ],
)
def test_ratio_inverts_the_observed_factor(f, ratio):
    """services/corporate_action_service uses 1/(1+ratio); it must give f back."""
    assert 1.0 / f - 1.0 == pytest.approx(ratio, abs=1e-6)
    assert 1.0 / (1.0 + (1.0 / f - 1.0)) == pytest.approx(f, abs=1e-9)
