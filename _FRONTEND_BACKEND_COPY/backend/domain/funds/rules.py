from __future__ import annotations


def validate_nav(nav: float) -> bool:
    return nav >= 0


def validate_unit_price(price: float) -> bool:
    return price >= 0


def validate_total_units(units: int) -> bool:
    return units >= 0


def validate_fund_type(fund_type: str) -> bool:
    valid_types = {
        "equity",
        "fixed_income",
        "mixed",
        "money_market",
        "index",
        "commodity",
        "real_estate",
        "hedge",
        "private_equity",
    }
    return fund_type in valid_types


def is_fund_active(status: str) -> bool:
    return status == "active"
