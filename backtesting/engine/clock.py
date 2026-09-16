from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta


class Clock:
    def __init__(self, start: datetime | None = None, end: datetime | None = None) -> None:
        self._now: datetime = start or datetime.now(UTC)
        self._start: datetime = self._now
        self._end: datetime = end or (self._now + timedelta(days=365))
        self._listeners: list[Callable[[datetime], None]] = []

    @property
    def now(self) -> datetime:
        return self._now

    def tick(self, delta: timedelta = timedelta(days=1)) -> None:
        self._now += delta
        for listener in self._listeners:
            listener(self._now)

    def jump_to(self, dt: datetime) -> None:
        self._now = dt

    def on_tick(self, listener: Callable[[datetime], None]) -> None:
        self._listeners.append(listener)

    def is_market_open(self, market_open: str = "09:00", market_close: str = "12:30") -> bool:
        try:
            t = self._now.time()
            open_h, open_m = map(int, market_open.split(":"))
            close_h, close_m = map(int, market_close.split(":"))

            if not (0 <= open_h < 24 and 0 <= open_m < 60):
                raise ValueError("Invalid market open time")
            if not (0 <= close_h < 24 and 0 <= close_m < 60):
                raise ValueError("Invalid market close time")

            open_t = t.replace(hour=open_h, minute=open_m, second=0)
            close_t = t.replace(hour=close_h, minute=close_m, second=0)
            return open_t <= t <= close_t
        except (ValueError, AttributeError) as e:
            raise ValueError(f"Invalid market hours format: {e}") from e

    def reset(self) -> None:
        self._now = self._start
