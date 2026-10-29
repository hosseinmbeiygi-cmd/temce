"""تست Scorer — 6 component + hard stop."""

from __future__ import annotations

from src.gold_desk.scorer import (
    compute_score,
    score_bubble,
    score_fund_flow,
    score_nav,
    score_parity,
    score_technical,
    score_tsetmc,
)

# ── score_bubble ────────────────────────────────────────────────


def test_bubble_optimal():
    c = score_bubble(3.0)  # < 8%
    assert c.value == 20
    assert "عالی" in c.reason


def test_bubble_yellow():
    c = score_bubble(10.0)  # 8-15
    assert c.value == 15  # 75% of 20


def test_bubble_orange():
    c = score_bubble(18.0)  # 15-22
    assert c.value == 8  # 40% of 20


def test_bubble_red():
    c = score_bubble(30.0)  # > 22
    assert c.value == 0


def test_bubble_none():
    c = score_bubble(None)
    assert c.value == 0
    assert "موجود نیست" in c.reason


# ── score_nav ───────────────────────────────────────────────────


def test_nav_optimal():
    c = score_nav(0.3)
    assert c.value == 18


def test_nav_warning():
    c = score_nav(2.0)  # 1.5-3
    assert c.value < 18
    assert c.value > 0


def test_nav_danger():
    c = score_nav(4.0)  # > 3
    assert c.value == 0


# ── score_tsetmc ────────────────────────────────────────────────


def test_tsetmc_strong_inflow():
    c = score_tsetmc(bpr=2.5, net_inflow=6e9)
    # 11 (BPR green) + 7 (inflow green) = 18 (max)
    assert c.value == 18


def test_tsetmc_no_data():
    c = score_tsetmc(bpr=None, net_inflow=None)
    assert c.value == 0


def test_tsetmc_weak():
    c = score_tsetmc(bpr=0.5, net_inflow=0)
    assert c.value == 0


# ── score_technical ─────────────────────────────────────────────


def test_rsi_optimal():
    c = score_technical(35.0)  # 30-45
    assert c.value == 15


def test_rsi_overbought():
    c = score_technical(75.0)  # > 70
    assert c.value == 0


def test_rsi_oversold():
    c = score_technical(20.0)  # < 30
    assert c.value == 9  # 60% of 15


# ── score_parity ────────────────────────────────────────────────


def test_parity_optimal():
    c = score_parity(0.3)  # |gap| < 0.5
    assert c.value == 15


def test_parity_high():
    c = score_parity(2.0)  # |gap| 1.5-3
    assert c.value < 15
    assert c.value > 0


def test_parity_extreme():
    c = score_parity(5.0)  # |gap| > 3
    assert c.value == 0


# ── score_fund_flow ─────────────────────────────────────────────


def test_fund_flow_strong():
    c = score_fund_flow(2.0)  # >= 1
    assert c.value == 14


def test_fund_flow_negative():
    c = score_fund_flow(-2.0)  # < -1
    assert c.value == 0


# ── compute_score ───────────────────────────────────────────────


def test_compute_green_scenario():
    """سناریوی ایده‌آل: همه چیز سبز (تقریباً)."""
    r = compute_score(
        bubble_pct=3.0,
        nav_bubble_pct=0.3,
        bpr=2.5,
        net_inflow=6e9,
        xau_rsi=35.0,
        aed_gap_pct=0.3,
        nav_7d_pct=2.0,
    )
    # همه چیز max → 100
    assert r.total >= 95
    assert r.decision == "GREEN"
    assert r.hard_stop_active is False


def test_compute_yellow_scenario():
    """وضعیت متوسط."""
    r = compute_score(
        bubble_pct=10.0,
        nav_bubble_pct=1.0,
        bpr=1.7,
        net_inflow=2e9,
        xau_rsi=55.0,
        aed_gap_pct=1.0,
        nav_7d_pct=0.5,
    )
    assert 55 <= r.total < 80
    assert r.decision == "YELLOW"


def test_compute_red_scenario():
    """وضعیت بحران."""
    r = compute_score(
        bubble_pct=30.0,
        nav_bubble_pct=5.0,
        bpr=0.5,
        net_inflow=0,
        xau_rsi=80.0,
        aed_gap_pct=5.0,
        nav_7d_pct=-3.0,
    )
    assert r.total < 55
    assert r.decision == "RED"


def test_compute_hard_stop_overrides():
    """hard_stop حتی در صورت امتیاز بالا → RED."""
    r = compute_score(
        bubble_pct=3.0,
        nav_bubble_pct=0.3,
        bpr=2.5,
        net_inflow=6e9,
        xau_rsi=35.0,
        aed_gap_pct=0.3,
        nav_7d_pct=2.0,
        hard_stop_active=True,
        hard_stop_reason="TSE crash",
    )
    assert r.decision == "RED"
    assert r.hard_stop_active is True
    assert r.hard_stop_reason == "TSE crash"


# ── E-L2/L3/L4: ثابت‌ها و مرزها ─────────────────


def test_tsetmc_point_split_matches_component_weight():
    """E-L2: ۱۱/۷ نباید جادویی باشد؛ جمعشان = وزن کامپوننت."""
    from src.gold_desk import constants

    assert (
        constants.SCORE_WEIGHTS["tsetmc"]
        == constants.TSETMC_BPR_GREEN_PTS + constants.TSETMC_INFLOW_GREEN_PTS
    )
    c = score_tsetmc(2.5, 6e9)
    assert c.value == constants.SCORE_WEIGHTS["tsetmc"]
    assert c.max_value == constants.SCORE_WEIGHTS["tsetmc"]


def test_threshold_boundaries_are_inclusive():
    """E-L4: مقدار دقیقاً برابر آستانهٔ *_MAX باید در خوشهٔ بهتر بماند."""
    from src.gold_desk import constants

    assert score_bubble(constants.BUBBLE_GREEN_MAX).value == constants.SCORE_WEIGHTS["bubble"]
    assert score_nav(constants.NAV_GREEN_MAX).value == constants.SCORE_WEIGHTS["nav"]
    assert score_parity(constants.PARITY_GREEN_MAX).value == constants.SCORE_WEIGHTS["parity"]
    assert score_technical(constants.RSI_GREEN_MIN).value == constants.SCORE_WEIGHTS["technical"]
    assert score_fund_flow(constants.FUND_FLOW_GREEN_MIN).value == constants.SCORE_WEIGHTS["fund_flow"]


def test_fund_flow_minor_drop_band_is_named():
    """E-L3: مرز -۱٪ باید از constants بیاید، نه عدد جادویی."""
    from src.gold_desk import constants

    assert -2.0 < constants.FUND_FLOW_MINOR_DROP_MAX < 0.0
    assert score_fund_flow(constants.FUND_FLOW_MINOR_DROP_MAX).value > 0
    assert score_fund_flow(constants.FUND_FLOW_MINOR_DROP_MAX - 0.1).value == 0


def test_low_coverage_gives_no_data():
    """E-C5: با یک کامپوننت از شش، امتیاز نباید GREEN شود.

    پیش از این نرمال‌سازی روی وزن موجود، ``bubble=7.9`` تنها را به ۱۰۰/GREEN می‌رساند.
    """
    r = compute_score(
        bubble_pct=7.9,
        nav_bubble_pct=None,
        bpr=None,
        net_inflow=None,
        xau_rsi=None,
        aed_gap_pct=None,
        nav_7d_pct=None,
    )
    assert r.available_weight == 20
    assert r.decision == "NO_DATA"
    # total عددی می‌ماند (برای نمودار) ولی مبنای تصمیم نیست
    assert isinstance(r.total, int)


def test_full_coverage_still_decides():
    """پوشش کامل نباید دست‌کاری شود."""
    r = compute_score(
        bubble_pct=3.0,
        nav_bubble_pct=0.3,
        bpr=2.5,
        net_inflow=6e9,
        xau_rsi=35.0,
        aed_gap_pct=0.3,
        nav_7d_pct=2.0,
    )
    assert r.available_weight == 100
    assert r.data_coverage_pct == 100.0
    assert r.decision == "GREEN"


def test_compute_score_bounds():
    """امتحان edge cases: داده None یا صفر."""
    r = compute_score(
        bubble_pct=None,
        nav_bubble_pct=None,
        bpr=None,
        net_inflow=None,
        xau_rsi=None,
        aed_gap_pct=None,
        nav_7d_pct=None,
    )
    assert 0 <= r.total <= 100
    # E-C5: پوشش صفر یعنی «داده نیست»، نه «قرمز» — تصمیم نباید از عدد ساخته شود.
    assert r.decision == "NO_DATA"
    assert r.available_weight == 0
