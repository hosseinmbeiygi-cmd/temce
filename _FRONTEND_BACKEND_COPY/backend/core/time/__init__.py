from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Literal

import pytz

from core.constants.markets import MARKET_WEEKEND_DAYS

IRAN_TZ = pytz.timezone("Asia/Tehran")
UTC = UTC


def now_utc() -> datetime:
    return datetime.now(UTC)


def now_tehran() -> datetime:
    return datetime.now(IRAN_TZ)


def now_iran() -> datetime:
    """Alias for now_tehran() — used by the pipeline enrichment modules."""
    return now_tehran()


def utc_now_naive() -> datetime:
    """Return current UTC time without tzinfo for legacy naive DB columns.

    New APIs should persist timezone-aware UTC values. This adapter is for
    existing ``DateTime(timezone=False)`` columns so comparisons stay
    consistent across machines regardless of the host timezone.
    """
    return now_utc().replace(tzinfo=None)


def utc_to_tehran(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(IRAN_TZ)


def tehran_to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = IRAN_TZ.localize(dt)
    return dt.astimezone(UTC)


def date_to_tehran(d: date) -> date:
    return d


def today_tehran() -> date:
    return now_tehran().date()


def today_utc() -> date:
    return now_utc().date()


def format_tehran(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    return utc_to_tehran(dt).strftime(fmt)


def parse_tehran(s: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> datetime:
    naive = datetime.strptime(s, fmt)
    return IRAN_TZ.localize(naive)


def parse_date_tehran(s: str, fmt: str = "%Y-%m-%d") -> date:
    return datetime.strptime(s, fmt).date()


def range_dates(start: date, end: date) -> list[date]:
    days = (end - start).days
    return [start + timedelta(days=i) for i in range(days + 1)]


def is_market_open(dt: datetime | None = None) -> bool:
    if dt is None:
        dt = now_tehran()
    if dt.weekday() in MARKET_WEEKEND_DAYS:
        return False
    market_open = dt.replace(hour=9, minute=0, second=0, microsecond=0)
    market_close = dt.replace(hour=12, minute=30, second=0, microsecond=0)
    return market_open <= dt <= market_close


def next_market_open(from_dt: datetime | None = None) -> datetime:
    if from_dt is None:
        from_dt = now_tehran()
    d = from_dt
    while True:
        if d.weekday() not in MARKET_WEEKEND_DAYS:
            return d.replace(hour=9, minute=0, second=0, microsecond=0)
        d += timedelta(days=1)


TimeFrame = Literal["1m", "5m", "15m", "30m", "1h", "1d", "1w", "1M"]


def timeframe_to_timedelta(tf: TimeFrame) -> timedelta:
    mapping: dict[str, timedelta] = {
        "1m": timedelta(minutes=1),
        "5m": timedelta(minutes=5),
        "15m": timedelta(minutes=15),
        "30m": timedelta(minutes=30),
        "1h": timedelta(hours=1),
        "1d": timedelta(days=1),
        "1w": timedelta(weeks=1),
        "1M": timedelta(days=30),
    }
    return mapping[tf]


def floor_to_timeframe(dt: datetime, tf: TimeFrame) -> datetime:
    if tf == "1d":
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    if tf == "1h":
        return dt.replace(minute=0, second=0, microsecond=0)
    if tf in ("5m", "15m", "30m"):
        minutes = int(tf[:-1])
        return dt.replace(minute=(dt.minute // minutes) * minutes, second=0, microsecond=0)
    if tf == "1m":
        return dt.replace(second=0, microsecond=0)
    if tf == "1w":
        monday = dt - timedelta(days=dt.weekday())
        return monday.replace(hour=0, minute=0, second=0, microsecond=0)
    return dt
