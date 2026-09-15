from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any

from core.constants.markets import MARKET_WEEKEND_DAYS
from core.time import IRAN_TZ, now_tehran


@dataclass
class MarketSession:
    name: str = ""
    open_time: time | None = None
    close_time: time | None = None
    is_active: bool = False

    def __init__(
        self,
        name: str = "",
        open_time: time | None = None,
        close_time: time | None = None,
        is_active: bool = False,
    ) -> None:
        self.name = name
        self.open_time = open_time
        self.close_time = close_time
        self.is_active = is_active

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "open_time": self.open_time.isoformat() if self.open_time else "",
            "close_time": self.close_time.isoformat() if self.close_time else "",
            "is_active": self.is_active,
        }

    def is_open(self, open_time: time, close_time: time, current_time: time | None = None) -> bool:
        if current_time is None:
            from core.time import now_tehran

            current_time = now_tehran().time()
        return open_time <= current_time < close_time

    def is_pre_open(self, current_time: time | None = None) -> bool:
        if current_time is None:
            from core.time import now_tehran

            current_time = now_tehran().time()
        return time(8, 30) <= current_time < time(9, 0)

    def is_post_close(self, current_time: time | None = None) -> bool:
        if current_time is None:
            from core.time import now_tehran

            current_time = now_tehran().time()
        return time(12, 30) <= current_time <= time(13, 0)

    def is_weekend(self, day_name: str) -> bool:
        weekends = {"thursday", "friday"}
        return day_name.strip().lower() in weekends


PRE_OPEN = MarketSession("pre_open", time(8, 30), time(9, 0))
CONTINUOUS = MarketSession("continuous", time(9, 0), time(12, 30))
POST_CLOSE = MarketSession("post_close", time(12, 30), time(13, 0))


def get_current_session(dt: datetime | None = None) -> MarketSession:
    if dt is None:
        dt = now_tehran()
    if dt.weekday() in MARKET_WEEKEND_DAYS:
        return MarketSession("closed", time(0, 0), time(0, 0))
    t = dt.time()
    if PRE_OPEN.open_time <= t < PRE_OPEN.close_time:
        return PRE_OPEN
    if CONTINUOUS.open_time <= t < CONTINUOUS.close_time:
        return CONTINUOUS
    if POST_CLOSE.open_time <= t < POST_CLOSE.close_time:
        return POST_CLOSE
    return MarketSession("closed", time(0, 0), time(0, 0))


def is_market_open(dt: datetime | None = None) -> bool:
    session = get_current_session(dt)
    return session.name in ("pre_open", "continuous")


def time_to_market_open(dt: datetime | None = None) -> timedelta:
    if dt is None:
        dt = now_tehran()
    if dt.weekday() in MARKET_WEEKEND_DAYS:
        next_day = dt + timedelta(days=1)
        while next_day.weekday() in MARKET_WEEKEND_DAYS:
            next_day += timedelta(days=1)
        market_open = datetime.combine(next_day.date(), CONTINUOUS.open_time, tzinfo=IRAN_TZ)
        return market_open - dt
    today_open = datetime.combine(dt.date(), CONTINUOUS.open_time, tzinfo=IRAN_TZ)
    if dt < today_open:
        return today_open - dt
    next_day = dt + timedelta(days=1)
    while next_day.weekday() in MARKET_WEEKEND_DAYS:
        next_day += timedelta(days=1)
    market_open = datetime.combine(next_day.date(), CONTINUOUS.open_time, tzinfo=IRAN_TZ)
    return market_open - dt


def time_to_market_close(dt: datetime | None = None) -> timedelta:
    if dt is None:
        dt = now_tehran()
    today_close = datetime.combine(dt.date(), CONTINUOUS.close_time, tzinfo=IRAN_TZ)
    return max(today_close - dt, timedelta(0))
