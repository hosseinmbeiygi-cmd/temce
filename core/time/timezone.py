from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytz

IRAN_TZ = pytz.timezone("Asia/Tehran")
UTC = UTC

TIMEZONES = {
    "tehran": "Asia/Tehran",
    "utc": "UTC",
    "new_york": "America/New_York",
    "london": "Europe/London",
    "tokyo": "Asia/Tokyo",
    "dubai": "Asia/Dubai",
}


def get_timezone(name: str) -> Any:
    tz_name = TIMEZONES.get(name.lower(), name)
    return pytz.timezone(tz_name)


def now_in_tz(tz_name: str) -> datetime:
    tz = get_timezone(tz_name)
    return datetime.now(tz)


def convert_tz(dt: datetime, target_tz: str) -> datetime:
    target = get_timezone(target_tz)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(target)


def localize(dt: datetime, tz_name: str) -> datetime:
    tz = get_timezone(tz_name)
    if dt.tzinfo is not None:
        return dt.astimezone(tz)
    return tz.localize(dt)


def is_dst(dt: datetime | None = None, tz_name: str = "Asia/Tehran") -> bool:
    if dt is None:
        dt = datetime.now()
    tz = get_timezone(tz_name)
    localized = localize(dt.replace(tzinfo=None), tz_name) if dt.tzinfo is None else dt.astimezone(tz)
    return bool(localized.dst()) if localized.dst() else False
