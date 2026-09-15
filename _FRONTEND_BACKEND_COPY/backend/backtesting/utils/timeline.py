from __future__ import annotations

from datetime import UTC, datetime, timedelta


class Timeline:
    def __init__(self, start: datetime | None = None, end: datetime | None = None) -> None:
        self._start = start or datetime.now(UTC)
        self._end = end or (self._start + timedelta(days=365))
        self._current = self._start

    @property
    def start(self) -> datetime:
        return self._start

    @property
    def end(self) -> datetime:
        return self._end

    @property
    def current(self) -> datetime:
        return self._current

    def advance(self, delta: timedelta = timedelta(days=1)) -> None:
        self._current += delta

    def is_finished(self) -> bool:
        return self._current >= self._end

    def days_remaining(self) -> int:
        return max(0, (self._end - self._current).days)

    def percentage_complete(self) -> float:
        total = (self._end - self._start).total_seconds()
        elapsed = (self._current - self._start).total_seconds()
        return min(100.0, (elapsed / total) * 100) if total > 0 else 100.0

    def generate_bars(self, frequency: str = "daily") -> list[datetime]:
        bars: list[datetime] = []
        current = self._start
        while current <= self._end:
            bars.append(current)
            if frequency == "daily":
                current += timedelta(days=1)
            elif frequency == "weekly":
                current += timedelta(weeks=1)
            elif frequency == "monthly":
                month = current.month + 1
                year = current.year + (month - 1) // 12
                month = ((month - 1) % 12) + 1
                current = current.replace(year=year, month=month)
            else:
                current += timedelta(days=1)
        return bars

    def reset(self) -> None:
        self._current = self._start

    def __repr__(self) -> str:
        return f"Timeline(start={self._start}, end={self._end}, current={self._current})"
