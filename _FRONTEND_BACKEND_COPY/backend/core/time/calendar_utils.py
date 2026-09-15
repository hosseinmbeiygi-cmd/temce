from __future__ import annotations

from datetime import date, timedelta

from core.constants.markets import MARKET_WEEKEND_DAYS


class CalendarUtils:
    @staticmethod
    def is_weekend(d: date) -> bool:
        return d.weekday() in MARKET_WEEKEND_DAYS

    @staticmethod
    def is_holiday(d: date, holidays: set[date] | None = None) -> bool:
        if CalendarUtils.is_weekend(d):
            return True
        return bool(holidays and d in holidays)

    @staticmethod
    def next_business_day(d: date, holidays: set[date] | None = None) -> date:
        d = d + timedelta(days=1)
        while CalendarUtils.is_holiday(d, holidays):
            d += timedelta(days=1)
        return d

    @staticmethod
    def previous_business_day(d: date, holidays: set[date] | None = None) -> date:
        d = d - timedelta(days=1)
        while CalendarUtils.is_holiday(d, holidays):
            d -= timedelta(days=1)
        return d

    @staticmethod
    def business_days_between(start: date, end: date, holidays: set[date] | None = None) -> list[date]:
        days: list[date] = []
        current = start
        while current <= end:
            if not CalendarUtils.is_holiday(current, holidays):
                days.append(current)
            current += timedelta(days=1)
        return days

    @staticmethod
    def count_business_days(start: date, end: date, holidays: set[date] | None = None) -> int:
        return len(CalendarUtils.business_days_between(start, end, holidays))

    @staticmethod
    def add_business_days(d: date, n: int, holidays: set[date] | None = None) -> date:
        current = d
        added = 0
        while added < n:
            current += timedelta(days=1)
            if not CalendarUtils.is_holiday(current, holidays):
                added += 1
        return current
