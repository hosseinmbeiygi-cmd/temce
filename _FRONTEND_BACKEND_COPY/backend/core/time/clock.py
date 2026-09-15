from __future__ import annotations

import time
from datetime import UTC, datetime


class Clock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def timestamp(self) -> float:
        return time.time()

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class SimulatedClock(Clock):
    def __init__(self, start_time: datetime | None = None) -> None:
        self._current_time = start_time or datetime(2024, 1, 1, tzinfo=UTC)
        self._speed = 1.0

    def set_speed(self, speed: float) -> None:
        self._speed = speed

    def advance(self, seconds: float) -> None:
        from datetime import timedelta

        self._current_time += timedelta(seconds=seconds * self._speed)

    def now(self) -> datetime:
        return self._current_time

    def timestamp(self) -> float:
        return self._current_time.timestamp()

    def sleep(self, seconds: float) -> None:
        self.advance(seconds)


_default_clock = Clock()


def get_clock() -> Clock:
    return _default_clock


def set_clock(clock: Clock) -> None:
    global _default_clock
    _default_clock = clock
