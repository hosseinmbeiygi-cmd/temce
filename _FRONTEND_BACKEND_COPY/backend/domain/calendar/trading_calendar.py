"""Iranian Trading Calendar for TSE, IFB, and IME.

Handles:
- Weekly closure on Thursday and Friday for TSE/IFB
- Official Iranian holidays (Shamsi & Qamari)
- Market-specific hours (TSE: 9:00-12:30, IME: 10:00-15:00)
- Expiry date adjustment (if expiry falls on holiday, move to previous trading day)
- Trading days count for theta calculation

Market hours:
- TSE/IFB: Saturday-Wednesday 9:00-12:30
- IME: Saturday-Thursday with different sessions
"""

from __future__ import annotations

from datetime import date, timedelta

from core.time import now_tehran

try:
    import jdatetime

    HAS_JDATETIME = True
except ImportError:
    HAS_JDATETIME = False


# Iranian official holidays (Shamsi calendar, approximate for 1403-1404)
# Format: (month, day) in Shamsi
SHAMSI_HOLIDAYS = [
    (1, 1),  # Nowruz
    (1, 2),  # Nowruz
    (1, 3),  # Nowruz
    (1, 4),  # Nowruz
    (1, 12),  # Islamic Republic Day
    (1, 13),  # Nature Day (Sizdah Bedar)
    (2, 14),  # Imam Ali assassination
    (2, 15),  # Imam Hassan martyrdom
    (3, 5),  # Imam Khomeini death
    (3, 6),  # Khatam al-Anbiya uprising
    (6, 15),  # Tasua (varies by year)
    (6, 16),  # Ashura (varies by year)
    (8, 20),  # Arbaeen (varies by year)
    (9, 28),  # Prophet Muhammad death (varies by year)
    (10, 1),  # Imam Sadiq martyrdom (varies by year)
    (11, 22),  # Victory of Islamic Revolution
    (12, 29),  # Nationalization of Oil Industry (sometimes)
]

# Qamari holidays that shift each year (approximate dates for 2024-2025)
QAMARI_HOLIDAYS_GREGORIAN_2024 = [
    # Tasua & Ashura (Muharram)
    date(2024, 7, 15),  # Tasua
    date(2024, 7, 16),  # Ashura
    # Arbaeen
    date(2024, 8, 24),
    # Prophet Muhammad & Imam Sadiq
    date(2024, 9, 15),
    date(2024, 9, 16),
    # Islamic Revolution & related
    date(2025, 2, 11),  # 22 Bahman
]

QAMARI_HOLIDAYS_GREGORIAN_2025 = [
    # Tasua & Ashura (Muharram 1447)
    date(2025, 7, 5),
    date(2025, 7, 6),
    # Arbaeen
    date(2025, 8, 13),
    # Prophet Muhammad & Imam Sadiq
    date(2025, 9, 4),
    date(2025, 9, 5),
    # Islamic Revolution
    date(2025, 2, 11),
]


class TradingCalendar:
    """Iranian trading calendar for TSE/IFB/IME."""

    def __init__(self, extra_holidays: list[date] | None = None):
        self.holidays: set[date] = set()
        self._init_base_holidays()
        if extra_holidays:
            self.holidays.update(extra_holidays)

    def _init_base_holidays(self) -> None:
        """Initialize with known holidays."""
        # Add Qamari holidays
        self.holidays.update(QAMARI_HOLIDAYS_GREGORIAN_2024)
        self.holidays.update(QAMARI_HOLIDAYS_GREGORIAN_2025)

        # Add Shamsi holidays by converting to Gregorian (approximate)
        if HAS_JDATETIME:
            current_year = jdatetime.date.today().year
            for shamsi_month, shamsi_day in SHAMSI_HOLIDAYS:
                try:
                    jd = jdatetime.date(current_year, shamsi_month, shamsi_day)
                    self.holidays.add(jd.togregorian())
                except ValueError:
                    pass

    def is_trading_day(self, d: date) -> bool:
        """Check if a date is a trading day for Iranian markets.

        Markets are closed on Fridays and official holidays.
        Saturday-Wednesday are trading days; Thursday and Friday are closed.
        """
        # Tehran equity markets trade Saturday through Wednesday; Thursday
        # and Friday are the weekly closure days.
        if d.weekday() in (3, 4):  # Thursday, Friday
            return False
        # Check holidays
        return d not in self.holidays

    def next_trading_day(self, from_date: date) -> date:
        """Find the next trading day after from_date."""
        current = from_date + timedelta(days=1)
        while not self.is_trading_day(current):
            current += timedelta(days=1)
        return current

    def previous_trading_day(self, from_date: date) -> date:
        """Find the last trading day before from_date."""
        current = from_date - timedelta(days=1)
        while not self.is_trading_day(current):
            current -= timedelta(days=1)
        return current

    def trading_days_between(self, start: date, end: date) -> int:
        """Count trading days between start and end (inclusive)."""
        if start > end:
            start, end = end, start
        count = 0
        current = start
        while current <= end:
            if self.is_trading_day(current):
                count += 1
            current += timedelta(days=1)
        return count

    def adjust_expiry(self, nominal_expiry: date) -> date:
        """Adjust option expiry date if it falls on a non-trading day.

        In Iranian markets, if expiry is on a holiday, it moves to the
        previous trading day.
        """
        if self.is_trading_day(nominal_expiry):
            return nominal_expiry
        return self.previous_trading_day(nominal_expiry)

    def get_trading_days_list(self, start: date, end: date) -> list[date]:
        """Get list of all trading days between start and end."""
        days = []
        current = start
        while current <= end:
            if self.is_trading_day(current):
                days.append(current)
            current += timedelta(days=1)
        return days

    def days_to_expiry(self, from_date: date, expiry: date) -> int:
        """Calculate trading days from from_date to expiry."""
        return self.trading_days_between(from_date, expiry)

    def market_open_time(self, market: str = "tse") -> str:
        """Return market open time."""
        times = {
            "tse": "09:00",
            "ifb": "09:00",
            "ime": "10:00",
        }
        return times.get(market, "09:00")

    def market_close_time(self, market: str = "tse") -> str:
        """Return market close time."""
        times = {
            "tse": "12:30",
            "ifb": "12:30",
            "ime": "15:00",
        }
        return times.get(market, "12:30")

    def is_market_open_now(self, market: str = "tse") -> bool:
        """Check if market is currently open (simplified)."""
        now = now_tehran()
        today = now.date()
        if not self.is_trading_day(today):
            return False

        open_str = self.market_open_time(market)
        close_str = self.market_close_time(market)
        current_time = now.strftime("%H:%M")
        return open_str <= current_time <= close_str
