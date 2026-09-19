"""Unit tests for the double-entry ledger pure logic (no DB required)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from services.fund_ledger import (  # noqa: E402
    build_fee_accrual_lines,
    build_unit_movement_lines,
    trial_balance_from_rows,
    validate_balanced,
)


def test_validate_balanced_accepts_balanced_entry() -> None:
    lines = [
        {"account_code": "CASH", "debit_amount": 1_000_000, "credit_amount": 0},
        {"account_code": "UNITS_LIABILITY", "debit_amount": 0, "credit_amount": 1_000_000},
    ]
    debit, credit = validate_balanced(lines)
    assert debit == credit == 1_000_000


def test_validate_balanced_rejects_unbalanced() -> None:
    with pytest.raises(ValueError):
        validate_balanced(
            [
                {"account_code": "CASH", "debit_amount": 100, "credit_amount": 0},
                {"account_code": "UNITS_LIABILITY", "debit_amount": 0, "credit_amount": 90},
            ]
        )


def test_validate_balanced_rejects_both_sides_on_one_line() -> None:
    with pytest.raises(ValueError):
        validate_balanced(
            [
                {"account_code": "CASH", "debit_amount": 100, "credit_amount": 100},
            ]
        )


def test_validate_balanced_rejects_empty() -> None:
    with pytest.raises(ValueError):
        validate_balanced([])


def test_build_unit_movement_lines_issue_and_redeem() -> None:
    issue = build_unit_movement_lines("ISSUE", 5_000_000, unit_delta=100)
    assert issue[0]["account_code"] == "CASH"
    assert issue[0]["debit_amount"] == 5_000_000
    assert issue[1]["account_code"] == "UNITS_LIABILITY"
    assert issue[1]["credit_amount"] == 5_000_000
    validate_balanced(issue)

    redeem = build_unit_movement_lines("REDEEM", 2_000_000, unit_delta=40)
    assert redeem[0]["account_code"] == "UNITS_LIABILITY"
    assert redeem[0]["debit_amount"] == 2_000_000
    assert redeem[1]["account_code"] == "CASH"
    validate_balanced(redeem)


def test_build_unit_movement_lines_distribution() -> None:
    lines = build_unit_movement_lines("DISTRIBUTION", 750_000)
    assert lines[0]["account_code"] == "RETAINED_EARNINGS"
    assert lines[1]["account_code"] == "DISTRIBUTION_PAYABLE"
    validate_balanced(lines)


def test_build_unit_movement_lines_transfer_is_non_cash() -> None:
    lines = build_unit_movement_lines("TRANSFER", 0, unit_delta=10)
    assert len(lines) == 1
    assert lines[0]["debit_amount"] == 0
    assert lines[0]["credit_amount"] == 0
    validate_balanced(lines)


def test_build_unit_movement_lines_rejects_unknown_type() -> None:
    with pytest.raises(ValueError):
        build_unit_movement_lines("UNKNOWN", 100)


def test_build_fee_accrual_lines() -> None:
    lines = build_fee_accrual_lines(123_000)
    assert lines[0]["account_code"] == "FEE_EXPENSE"
    assert lines[0]["debit_amount"] == 123_000
    assert lines[1]["account_code"] == "FEE_PAYABLE"
    validate_balanced(lines)


def test_trial_balance_from_rows_computes_signed_balances() -> None:
    rows = [
        ("CASH", "نقد", "ASSET", "DEBIT", 1_000_000, 400_000),
        ("UNITS_LIABILITY", "سرمایه واحدها", "EQUITY", "CREDIT", 0, 600_000),
    ]
    result = trial_balance_from_rows(rows)
    assert result["balanced"] is True
    assert result["accounts"][0]["balance"] == 600_000  # debit-normal
    assert result["accounts"][1]["balance"] == 600_000  # credit-normal
    assert result["total_debit"] == result["total_credit"] == 1_000_000


def test_trial_balance_detects_unbalanced_books() -> None:
    rows = [("CASH", "نقد", "ASSET", "DEBIT", 100, 0)]
    result = trial_balance_from_rows(rows)
    assert result["balanced"] is False
