"""Unit tests for the independent NAV engine + reconciliation pure logic.

این تست‌ها بدون DB اجرا می‌شوند و «قرارداد محاسباتی» را قفل می‌کنند:
  * قطعیت ``input_hash`` (بازتولیدپذیری)
  * دروازه کیفیت داده (COMPLETE/ESTIMATED/PARTIAL/BLOCKED)
  * محاسبه NAV و محافظ واحد نامعتبر
  * ارزش‌گذاری ردیفی (قیمت لایو در برابر ارزش گزارش دوره)
  * آستانه دوگانه تطبیق + سه بُعد وضعیت + چرخه عمر پرونده مغایرت
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from services.fund_nav_engine import (  # noqa: E402
    build_input_hash,
    compute_nav,
    quality_from_coverage,
    value_position,
)
from services.fund_nav_reconciliation import (  # noqa: E402
    DEFAULT_THRESHOLDS,
    build_probable_cause,
    classify_diff,
    compute_diff,
    evaluate_comparability,
    evaluate_reference_status,
    next_lifecycle,
    summarize_shadow_acceptance,
)

# ── Engine ──────────────────────────────────────────────────────────────────


def test_input_hash_is_deterministic_and_order_insensitive() -> None:
    a = build_input_hash({"b": 2, "a": 1, "positions": [{"x": 1}]})
    b = build_input_hash({"positions": [{"x": 1}], "a": 1, "b": 2})
    assert a == b
    assert len(a) == 64


def test_input_hash_changes_with_input() -> None:
    a = build_input_hash({"units": 100})
    b = build_input_hash({"units": 101})
    assert a != b


@pytest.mark.parametrize(
    ("coverage", "units", "has_positions", "has_report", "expected"),
    [
        (100.0, 1000, True, True, "COMPLETE"),
        (80.0, 1000, True, True, "ESTIMATED"),
        (20.0, 1000, True, True, "PARTIAL"),
        (100.0, None, True, True, "BLOCKED"),
        (100.0, 0, True, True, "BLOCKED"),
        (100.0, 1000, False, True, "BLOCKED"),
        (97.0, 1000, True, False, "ESTIMATED"),
    ],
)
def test_quality_from_coverage(
    coverage: float, units: int | None, has_positions: bool, has_report: bool, expected: str
) -> None:
    assert quality_from_coverage(coverage, units, has_positions, has_report) == expected


def test_compute_nav_basic() -> None:
    net, nav = compute_nav(1_000_000_000, 100_000_000, 1000)
    assert net == 900_000_000
    assert nav == 900_000


def test_compute_nav_guards_invalid_units() -> None:
    assert compute_nav(1_000, 0, None) == (None, None)
    assert compute_nav(1_000, 0, 0) == (None, None)
    assert compute_nav(None, 0, 100) == (None, None)


def test_value_position_prefers_live_price_for_equity() -> None:
    holding = {
        "holding_type": "equity",
        "instrument_symbol": "فولاد",
        "quantity": 200,
        "market_value": 1_000_000,
    }
    pos = value_position(holding, live_price=6_000, price_at=datetime(2026, 9, 18, 10, 0))
    assert pos["quality"] == "LIVE"
    assert pos["price_source"] == "snapshot"
    assert pos["value"] == 1_200_000


def test_value_position_falls_back_to_reported_for_equity() -> None:
    holding = {
        "holding_type": "equity",
        "instrument_symbol": "فولاد",
        "quantity": 200,
        "market_value": 1_000_000,
    }
    pos = value_position(holding, live_price=None)
    assert pos["quality"] == "REPORTED"
    assert pos["value"] == 1_000_000
    assert pos["note"]


def test_value_position_non_equity_uses_report() -> None:
    holding = {"holding_type": "cash", "quantity": 0, "market_value": 500_000}
    pos = value_position(holding, live_price=999)
    assert pos["quality"] == "REPORTED"
    assert pos["value"] == 500_000


# ── Reconciliation ──────────────────────────────────────────────────────────


def test_compute_diff_bps_and_zero_reference_guard() -> None:
    delta, bps = compute_diff(1_010, 1_000)
    assert delta == 10
    assert bps == pytest.approx(100.0)

    delta0, bps0 = compute_diff(100, 0)
    assert delta0 == 100
    assert bps0 is None


def test_classify_diff_dual_threshold() -> None:
    th = dict(DEFAULT_THRESHOLDS)
    # داخل محدوده
    assert classify_diff(100, 1.0, th) == "MATCHED"
    # عبور از آستانه مطلق هشدار
    assert classify_diff(2_000_000, 1.0, th) == "WARNING"
    # عبور از آستانه bps هشدار (مبلغ کوچک)
    assert classify_diff(500, 15.0, th) == "WARNING"
    # عبور از آستانه بحرانی bps
    assert classify_diff(500, 60.0, th) == "BREACH"
    # عبور از آستانه بحرانی مطلق
    assert classify_diff(20_000_000, 1.0, th) == "BREACH"
    assert classify_diff(None, None, th) is None


def test_reference_status_valid_stale_invalid() -> None:
    today = date(2026, 9, 18)
    assert evaluate_reference_status(1000, today, today) == "VALID"
    assert evaluate_reference_status(1000, today - timedelta(days=6), today) == "STALE"
    assert evaluate_reference_status(None, today, today) == "INVALID"
    assert evaluate_reference_status(0, today, today) == "INVALID"
    assert evaluate_reference_status(1000, None, today) == "INVALID"


def test_comparability_gates() -> None:
    assert evaluate_comparability("COMPLETE", True, "VALID") == "COMPARABLE"
    assert evaluate_comparability("BLOCKED", True, "VALID") == "INCOMPLETE"
    assert evaluate_comparability("COMPLETE", False, "VALID") == "NOT_COMPARABLE"
    assert evaluate_comparability("COMPLETE", True, "STALE") == "NOT_COMPARABLE"
    assert evaluate_comparability("COMPLETE", True, "INVALID") == "NOT_COMPARABLE"


def test_break_lifecycle_transitions() -> None:
    assert next_lifecycle("OPEN", "INVESTIGATING") == "INVESTIGATING"
    assert next_lifecycle("INVESTIGATING", "RESOLVED") == "RESOLVED"
    assert next_lifecycle("ESCALATED", "ACCEPTED") == "ACCEPTED"
    with pytest.raises(ValueError):
        next_lifecycle("ACCEPTED", "OPEN")
    with pytest.raises(ValueError):
        next_lifecycle("OPEN", "UNKNOWN")


def _acceptance_rows(days: int, diff_status: str = "MATCHED", quality: str = "COMPLETE"):
    return [
        {
            "valuation_date": f"2026-08-{i + 1:02d}",
            "quality_status": quality,
            "coverage_pct": 99.0,
            "comparability_status": "COMPARABLE",
            "diff_status": diff_status,
        }
        for i in range(days)
    ]


def test_shadow_acceptance_ready_after_enough_clean_days() -> None:
    summary = summarize_shadow_acceptance(_acceptance_rows(21))
    assert summary["days"] == 21
    assert summary["match_rate"] == 1.0
    assert summary["acceptance_ready"] is True


def test_shadow_acceptance_not_ready_with_breach_or_blocked() -> None:
    rows = _acceptance_rows(21)
    rows[0]["diff_status"] = "BREACH"
    assert summarize_shadow_acceptance(rows)["acceptance_ready"] is False

    blocked = _acceptance_rows(21, quality="BLOCKED")
    assert summarize_shadow_acceptance(blocked)["acceptance_ready"] is False


def test_shadow_acceptance_not_ready_with_few_days() -> None:
    summary = summarize_shadow_acceptance(_acceptance_rows(5))
    assert summary["acceptance_ready"] is False
    assert summary["days"] == 5


# ── build_probable_cause ─────────────────────────────────────────────────────

_TODAY = date(2026, 11, 17)


def test_probable_cause_blocked_quality_is_critical() -> None:
    result = build_probable_cause(
        internal={"quality_status": "BLOCKED", "coverage_pct": 0},
        reference={},
        comparability="INCOMPLETE",
        reference_status="INVALID",
        valuation_date=_TODAY,
        reference_date=None,
    )
    codes = [c["code"] for c in result["causes"]]
    assert "BLOCKED_QUALITY" in codes
    primary = result["summary"]["primary_code"]
    assert primary == "BLOCKED_QUALITY"
    assert result["summary"]["primary_severity"] == "CRITICAL"


def test_probable_cause_stale_holdings_flagged() -> None:
    stale_period = _TODAY - timedelta(days=45)
    result = build_probable_cause(
        internal={"quality_status": "ESTIMATED", "coverage_pct": 80, "holdings_period": stale_period},
        reference={},
        comparability="COMPARABLE",
        reference_status="VALID",
        valuation_date=_TODAY,
        reference_date=_TODAY,
    )
    stale = next((c for c in result["causes"] if c["code"] == "STALE_HOLDINGS"), None)
    assert stale is not None
    assert stale["severity"] == "HIGH"
    assert stale["staleness_days"] == 45


def test_probable_cause_coverage_gap_flagged() -> None:
    result = build_probable_cause(
        internal={"quality_status": "PARTIAL", "coverage_pct": 60},
        reference={},
        comparability="COMPARABLE",
        reference_status="VALID",
        valuation_date=_TODAY,
        reference_date=_TODAY,
    )
    gap = next((c for c in result["causes"] if c["code"] == "COVERAGE_GAP"), None)
    assert gap is not None
    assert gap["coverage_gap_pct"] == 40.0


def test_probable_cause_units_mismatch_flagged() -> None:
    result = build_probable_cause(
        internal={"quality_status": "COMPLETE", "coverage_pct": 98, "units_outstanding": 1_000_000},
        reference={"units_outstanding": 1_200_000},
        comparability="COMPARABLE",
        reference_status="VALID",
        valuation_date=_TODAY,
        reference_date=_TODAY,
    )
    um = next((c for c in result["causes"] if c["code"] == "UNITS_MISMATCH"), None)
    assert um is not None
    assert um["severity"] == "HIGH"


def test_probable_cause_date_mismatch_flagged() -> None:
    ref_date = _TODAY - timedelta(days=2)
    result = build_probable_cause(
        internal={"quality_status": "COMPLETE", "coverage_pct": 98},
        reference={},
        comparability="NOT_COMPARABLE",
        reference_status="VALID",
        valuation_date=_TODAY,
        reference_date=ref_date,
    )
    dm = next((c for c in result["causes"] if c["code"] == "DATE_MISMATCH"), None)
    assert dm is not None
    assert dm["lag_days"] == 2


def test_probable_cause_unknown_when_all_clean() -> None:
    result = build_probable_cause(
        internal={"quality_status": "COMPLETE", "coverage_pct": 99},
        reference={},
        comparability="COMPARABLE",
        reference_status="VALID",
        valuation_date=_TODAY,
        reference_date=_TODAY,
    )
    assert result["causes"][0]["code"] == "UNKNOWN"
    assert result["summary"]["primary_severity"] == "LOW"


def test_probable_cause_sorted_by_severity() -> None:
    stale_period = _TODAY - timedelta(days=50)
    result = build_probable_cause(
        internal={"quality_status": "BLOCKED", "coverage_pct": 50, "holdings_period": stale_period},
        reference={},
        comparability="INCOMPLETE",
        reference_status="STALE",
        valuation_date=_TODAY,
        reference_date=_TODAY - timedelta(days=3),
    )
    severities = [c["severity"] for c in result["causes"]]
    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    assert severities == sorted(severities, key=lambda s: order[s])
