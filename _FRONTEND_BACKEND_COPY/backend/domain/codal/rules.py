from __future__ import annotations

from datetime import date

VALID_DISCLOSURE_TYPES = {"annual", "quarterly", "monthly", "extraordinary", "board_report", "auditor_report"}
VALID_PERIODS = {"12M", "9M", "6M", "3M", "1M"}


def validate_disclosure_type(disclosure_type: str) -> bool:
    return disclosure_type in VALID_DISCLOSURE_TYPES


def validate_period(period: str) -> bool:
    return period in VALID_PERIODS


def validate_fiscal_year(fiscal_year: str) -> bool:
    return len(fiscal_year) == 4 and fiscal_year.isdigit()


def validate_publish_date(publish_date: date | None) -> bool:
    if publish_date is None:
        return True
    return publish_date <= date.today()
