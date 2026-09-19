"""Unit tests for compliance pure logic (no DB required)."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from services.fund_compliance import (  # noqa: E402
    DEFAULT_CASH_THRESHOLD,
    assess_movement,
    reconcile_units,
    str_due_at,
)


def test_assess_movement_below_threshold_returns_none() -> None:
    assert assess_movement({"movement_type": "ISSUE", "amount": 100_000}, 1_000_000) is None


def test_assess_movement_above_threshold_flags_medium() -> None:
    alert = assess_movement({"movement_type": "REDEEM", "amount": 2_000_000}, 1_000_000)
    assert alert is not None
    assert alert["risk_level"] == "MEDIUM"
    assert alert["alert_type"] == "LARGE_CASH_REDEEM"


def test_assess_movement_ten_x_threshold_flags_high() -> None:
    alert = assess_movement({"movement_type": "ISSUE", "amount": 15_000_000}, 1_000_000)
    assert alert is not None
    assert alert["risk_level"] == "HIGH"


def test_assess_movement_ignores_non_cash_types() -> None:
    assert assess_movement({"movement_type": "TRANSFER", "amount": 9_000_000_000}) is None


def test_default_threshold_is_parametric() -> None:
    assert DEFAULT_CASH_THRESHOLD == 1_000_000_000.0


def test_str_due_at_is_same_day_plus_hours() -> None:
    base = datetime(2026, 9, 18, 9, 0, 0)
    assert str_due_at(base) == base + timedelta(hours=8)


def test_reconcile_units_matched_and_breach() -> None:
    assert reconcile_units(1000, 1000)["status"] == "MATCHED"
    assert reconcile_units(1000, 1005, tolerance=10)["status"] == "MATCHED"
    breach = reconcile_units(1000, 1005)
    assert breach["status"] == "BREACH"
    assert breach["units_diff"] == 5


def test_reconcile_units_incomplete_on_missing_side() -> None:
    assert reconcile_units(None, 1000)["status"] == "INCOMPLETE"
    assert reconcile_units(1000, None)["status"] == "INCOMPLETE"
