from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pytz

TEHRAN_TZ = pytz.timezone("Asia/Tehran")

IRAN_HOLIDAYS: set[str] = {
    "2024-01-01",
    "2024-03-20",
    "2024-03-21",
    "2024-03-22",
    "2024-03-23",
    "2024-03-24",
    "2024-04-01",
    "2024-04-02",
    "2024-04-10",
    "2024-04-11",
    "2024-06-04",
    "2024-06-05",
    "2024-06-16",
    "2024-06-17",
    "2024-06-18",
    "2024-07-25",
    "2024-07-26",
    "2024-08-21",
    "2024-08-22",
    "2024-09-04",
    "2024-12-01",
    "2024-12-02",
    "2025-01-01",
    "2025-03-10",
    "2025-03-11",
    "2025-03-12",
    "2025-03-13",
    "2025-03-14",
    "2025-03-21",
    "2025-03-22",
    "2025-03-23",
    "2025-03-24",
    "2025-03-31",
    "2025-04-01",
    "2025-04-10",
    "2025-04-11",
    "2025-05-25",
    "2025-05-26",
    "2025-06-04",
    "2025-06-05",
    "2025-06-06",
    "2025-07-14",
    "2025-07-15",
    "2025-08-11",
    "2025-08-12",
    "2025-08-25",
    "2025-11-21",
    "2025-11-22",
    "2025-12-20",
    "2025-12-21",
    "2026-01-01",
}


@dataclass
class TradingSession:
    date: date
    is_trading_day: bool = True
    session_type: str = "full"
    open_time: str = "09:00"
    close_time: str = "12:30"


class IranTradingCalendar:
    def __init__(self) -> None:
        self._holidays = IRAN_HOLIDAYS
        self._half_days: set[str] = set()
        self._sessions: dict[date, TradingSession] = {}

    def is_holiday(self, d: date) -> bool:
        # Python weekday(): Thursday=3, Friday=4. Tehran equity markets
        # trade Saturday through Wednesday.
        return d.weekday() in (3, 4) or d.isoformat() in self._holidays

    def is_trading_day(self, d: date) -> bool:
        return not self.is_holiday(d)

    def next_trading_day(self, d: date) -> date:
        current = d + timedelta(days=1)
        while self.is_holiday(current):
            current += timedelta(days=1)
        return current

    def prev_trading_day(self, d: date) -> date:
        current = d - timedelta(days=1)
        while self.is_holiday(current):
            current -= timedelta(days=1)
        return current

    def trading_days_between(self, start: date, end: date) -> list[date]:
        days: list[date] = []
        current = start
        while current <= end:
            if self.is_trading_day(current):
                days.append(current)
            current += timedelta(days=1)
        return days

    def trading_days_count(self, start: date, end: date) -> int:
        return len(self.trading_days_between(start, end))

    def market_open_time(self, d: date) -> str:
        session = self._sessions.get(d)
        return session.open_time if session else "09:00"

    def market_close_time(self, d: date) -> str:
        session = self._sessions.get(d)
        return session.close_time if session else "12:30"

    def get_session(self, d: date) -> TradingSession:
        if d in self._sessions:
            return self._sessions[d]
        return TradingSession(
            date=d,
            is_trading_day=self.is_trading_day(d),
            session_type="half" if d.isoformat() in self._half_days else "full",
        )
