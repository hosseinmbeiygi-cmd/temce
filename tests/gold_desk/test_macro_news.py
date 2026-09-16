"""تست Macro/News — pure functions."""

from __future__ import annotations

from datetime import timedelta

from core.time import utc_now_naive
from src.gold_desk.macro_news import (
    MacroEvent,
    compute_macro_multiplier,
    estimate_impact,
    get_sample_events,
)


def test_sample_events_have_required_fields():
    events = get_sample_events()
    assert len(events) >= 3
    for e in events:
        assert e.title
        assert e.source in ("cbi", "markaz_amar", "wgc", "news")
        assert e.category in ("rate", "inflation", "fx", "demand", "geopolitics")
        assert -3 <= e.impact_score <= 3
        assert 0 <= e.confidence <= 1


def test_estimate_impact_rate_up():
    score, conf = estimate_impact("نرخ بهره افزایش یافت", "rate")
    assert score < 0  # نرخ بالا = منفی برای طلا


def test_estimate_impact_rate_down():
    score, conf = estimate_impact("نرخ بهره کاهش یافت", "rate")
    assert score > 0


def test_estimate_impact_inflation_up():
    score, _ = estimate_impact("تورم افزایش یافت", "inflation")
    assert score > 0  # تورم = مثبت


def test_estimate_impact_fx_strong():
    score, _ = estimate_impact("دلار تقویت شد", "fx")
    assert score < 0  # دلار قوی = منفی


def test_estimate_impact_demand_high():
    score, _ = estimate_impact("تقاضا افزایش یافت", "demand")
    assert score > 0


def test_compute_macro_multiplier_empty():
    assert compute_macro_multiplier([]) == 0.0


def test_compute_macro_multiplier_recent():
    """رویداد اخیر مثبت → multiplier > 0."""
    now = utc_now_naive()
    events = [
        MacroEvent(
            title="test",
            source="cbi",
            category="inflation",
            impact_score=+2,
            confidence=0.8,
            explanation="",
            published_at=now,
        ),
    ]
    mult = compute_macro_multiplier(events)
    assert mult > 0


def test_compute_macro_multiplier_old_events_decay():
    """رویداد قدیمی = وزن کم."""
    now = utc_now_naive()
    old = MacroEvent(
        title="old",
        source="cbi",
        category="inflation",
        impact_score=+3,
        confidence=1.0,
        explanation="",
        published_at=now - timedelta(days=60),
    )
    recent = MacroEvent(
        title="recent",
        source="cbi",
        category="fx",
        impact_score=-1,
        confidence=0.5,
        explanation="",
        published_at=now,
    )
    mult = compute_macro_multiplier([old, recent])
    # recent باید وزن بیشتری داشته باشه
    assert mult < 0  # recent negative dominates


def test_compute_macro_multiplier_bounds():
    """خروجی همیشه بین -1 و +1."""
    now = utc_now_naive()
    extreme = [
        MacroEvent(
            title="x",
            source="cbi",
            category="rate",
            impact_score=score,
            confidence=1.0,
            explanation="",
            published_at=now,
        )
        for score in [-3, 3]
    ]
    mult_pos = compute_macro_multiplier([extreme[1]])
    mult_neg = compute_macro_multiplier([extreme[0]])
    assert -1 <= mult_pos <= 1
    assert -1 <= mult_neg <= 1
