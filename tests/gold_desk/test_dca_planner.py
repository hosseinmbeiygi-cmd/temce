"""تست DCA Planner."""

from __future__ import annotations

import pytest

from src.gold_desk.dca_planner import plan_dca


def test_plan_basic():
    plan = plan_dca(
        total_capital_irt=100_000_000,
        risk_profile="balanced",
        current_score=70,
    )
    assert plan.total_capital_irt == 100_000_000
    assert len(plan.ladder) == 3
    # 30/40/30
    assert plan.ladder[0].pct == 0.30
    assert plan.ladder[1].pct == 0.40
    assert plan.ladder[2].pct == 0.30
    # مبلغ‌ها به نسبت ۳۰/۴۰/۳۰ از مبلغ خالص (پس از کارمزد) — E-M15
    assert plan.ladder[0].amount_irt == pytest.approx(plan.net_investable_irt * 0.30)
    assert plan.ladder[1].amount_irt == pytest.approx(plan.net_investable_irt * 0.40)
    assert plan.ladder[2].amount_irt == pytest.approx(plan.net_investable_irt * 0.30)


def test_ladder_is_internally_consistent():
    """E-M15: مجموع پله‌ها = net_investable، و پله+کارمزد = سرمایه."""
    for vehicle in ("etf", "cert", "melted", "coin", "jewelry"):
        plan = plan_dca(100_000_000, "balanced", 70, preferred_vehicle=vehicle)
        assert sum(t.amount_irt for t in plan.ladder) == pytest.approx(plan.net_investable_irt)
        assert plan.net_investable_irt + plan.total_fee_irt == pytest.approx(100_000_000)
        assert sum(t.estimated_fee_irt for t in plan.ladder) == pytest.approx(plan.total_fee_irt)
        # نه پله‌ای بیش از سرمایه می‌خواهد و نه پولی گم می‌شود
        assert sum(t.amount_irt + t.estimated_fee_irt for t in plan.ladder) == pytest.approx(
            100_000_000
        )


def test_plan_conservative():
    plan = plan_dca(100_000_000, "conservative", 85)
    assert plan.ladder[0].pct == 0.20
    assert plan.ladder[1].pct == 0.40
    assert plan.ladder[2].pct == 0.40
    # stop/take profit محافظه‌کارانه
    assert plan.stop_loss_pct == 5.0
    assert plan.take_profit_pct == 20.0


def test_plan_aggressive():
    plan = plan_dca(100_000_000, "aggressive", 55)
    assert plan.ladder[0].pct == 0.50
    assert plan.ladder[1].pct == 0.30
    assert plan.ladder[2].pct == 0.20
    # stop/take profit ریسکی
    assert plan.stop_loss_pct == 12.0
    assert plan.take_profit_pct == 35.0


def test_plan_vehicle_recommendation_high_score():
    """امتیاز بالا → ETF (کارمزد کم)."""
    plan = plan_dca(100_000_000, "balanced", 80)
    assert plan.recommended_vehicle == "etf"


def test_plan_vehicle_recommendation_low_score():
    """امتیاز پایین → melted (سرمایه‌گذاری بلندمدت)."""
    plan = plan_dca(100_000_000, "balanced", 50)
    assert plan.recommended_vehicle == "melted"


def test_plan_fee_calculation():
    """محاسبه fee دقیق برای ETF (0.15%)."""
    plan = plan_dca(100_000_000, "balanced", 80, preferred_vehicle="etf")
    # کارمزد روی مبلغ خالص گرفته می‌شود: fee = C × r/(1+r) برای C=100M، r=0.15%
    assert abs(plan.total_fee_irt - 149_775) < 100
    assert abs(plan.net_investable_irt - (100_000_000 - plan.total_fee_irt)) < 1e-6


def test_plan_fee_jewelry():
    """طلای زینتی کارمزد بالا (~18%)."""
    plan = plan_dca(100_000_000, "balanced", 70, preferred_vehicle="jewelry")
    # E-M15: کارمزد روی مبلغ خالص است ⇒ 100M × 0.18/1.18 ≈ 15.25M (نه ۱۸M)
    assert plan.total_fee_irt > 15_000_000
    assert plan.total_fee_irt < 15_500_000


def test_plan_invalid_capital():
    with pytest.raises(ValueError):
        plan_dca(0, "balanced", 60)
    with pytest.raises(ValueError):
        plan_dca(-1000, "balanced", 60)


def test_plan_invalid_score():
    with pytest.raises(ValueError):
        plan_dca(100_000_000, "balanced", 150)
    with pytest.raises(ValueError):
        plan_dca(100_000_000, "balanced", -10)


def test_plan_invalid_risk_profile():
    with pytest.raises(ValueError):
        plan_dca(100_000_000, "ultra_risky", 60)


def test_plan_preferred_vehicle_overrides():
    plan = plan_dca(100_000_000, "balanced", 80, preferred_vehicle="coin")
    assert plan.recommended_vehicle == "coin"


def test_plan_tranche_triggers_not_empty():
    plan = plan_dca(100_000_000, "balanced", 70)
    for t in plan.ladder:
        assert t.trigger
        assert len(t.trigger) > 5
