from __future__ import annotations

from datetime import date


def validate_coupon_rate(rate: float) -> bool:
    return 0.0 <= rate <= 1.0


def validate_face_value(value: float) -> bool:
    return value > 0


def validate_maturity_date(issue_date: date | None, maturity_date: date | None) -> bool:
    if issue_date is None or maturity_date is None:
        return True
    return maturity_date > issue_date


def validate_bond_yield(ytm: float) -> bool:
    return ytm >= 0.0


def is_investment_grade(rating: str) -> bool:
    return rating.upper() in ("AAA", "AA", "A", "BBB")
