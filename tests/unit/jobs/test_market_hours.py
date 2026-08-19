"""Unit tests for the Tehran trading-hours helper.

Covers:
  - ``_in_window`` weekday/weekend and boundary logic
  - ``is_tehran_market_open`` for market window (08:45–12:30, Sat–Wed)
  - ``is_tehran_codal_window`` for the wider Codal window (08:00–18:00)
  - fail-open behaviour on timezone errors

Uses a fake clock injected into ``_in_window`` directly — no real tz lookup.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest

from jobs.market_hours import (
    CODAL_CLOSE_HOUR,
    CODAL_CLOSE_MINUTE,
    CODAL_OPEN_HOUR,
    CODAL_OPEN_MINUTE,
    MARKET_CLOSE_HOUR,
    MARKET_CLOSE_MINUTE,
    MARKET_OPEN_HOUR,
    MARKET_OPEN_MINUTE,
    _in_window,
    is_tehran_codal_window,
    is_tehran_market_open,
)

# Python weekday(): Mon=0 … Thu=3, Fri=4, Sat=5, Sun=6
_SATURDAY = datetime(2026, 1, 3, 10, 0)  # weekday() == 5
_SUNDAY = datetime(2026, 1, 4, 10, 0)    # weekday() == 6
_MONDAY = datetime(2026, 1, 5, 10, 0)    # weekday() == 0
_THURSDAY = datetime(2026, 1, 8, 10, 0)  # weekday() == 3
_FRIDAY = datetime(2026, 1, 9, 10, 0)    # weekday() == 4


class TestInWindow:
    def test_weekend_days_are_closed(self) -> None:
        assert _in_window(_THURSDAY, 8, 0, 18, 0) is False
        assert _in_window(_FRIDAY, 8, 0, 18, 0) is False

    def test_inside_window(self) -> None:
        assert _in_window(_MONDAY, 8, 45, 12, 30) is True

    def test_before_open(self) -> None:
        early = datetime(2026, 1, 5, 8, 0)
        assert _in_window(early, MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE,
                          MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE) is False

    def test_after_close(self) -> None:
        late = datetime(2026, 1, 5, 13, 0)
        assert _in_window(late, MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE,
                          MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE) is False

    def test_boundaries_inclusive(self) -> None:
        open_exact = datetime(2026, 1, 5, 8, 45)
        close_exact = datetime(2026, 1, 5, 12, 30)
        assert _in_window(open_exact, 8, 45, 12, 30) is True
        assert _in_window(close_exact, 8, 45, 12, 30) is True


class TestIsTehranMarketOpen:
    @pytest.mark.asyncio
    async def test_open_during_trading_hours(self) -> None:
        # Monday 10:00 Tehran → inside 08:45–12:30.
        with patch("jobs.market_hours._now_tehran", return_value=_MONDAY.replace(hour=10, minute=0)):
            assert is_tehran_market_open() is True

    @pytest.mark.asyncio
    async def test_closed_before_open(self) -> None:
        with patch("jobs.market_hours._now_tehran", return_value=_MONDAY.replace(hour=8, minute=0)):
            assert is_tehran_market_open() is False

    @pytest.mark.asyncio
    async def test_closed_after_close(self) -> None:
        with patch("jobs.market_hours._now_tehran", return_value=_MONDAY.replace(hour=13, minute=0)):
            assert is_tehran_market_open() is False

    @pytest.mark.asyncio
    async def test_closed_on_weekend(self) -> None:
        with patch("jobs.market_hours._now_tehran", return_value=_FRIDAY):
            assert is_tehran_market_open() is False

    @pytest.mark.asyncio
    async def test_fail_open_on_error(self) -> None:
        with patch("jobs.market_hours._now_tehran", side_effect=RuntimeError("tz broken")):
            assert is_tehran_market_open() is True


class TestIsTehranCodalWindow:
    @pytest.mark.asyncio
    async def test_open_during_codal_hours(self) -> None:
        # Monday 15:00 → after market close but inside Codal window.
        with patch("jobs.market_hours._now_tehran", return_value=_MONDAY.replace(hour=15, minute=0)):
            assert is_tehran_codal_window() is True

    @pytest.mark.asyncio
    async def test_closed_at_night(self) -> None:
        with patch("jobs.market_hours._now_tehran", return_value=_MONDAY.replace(hour=20, minute=0)):
            assert is_tehran_codal_window() is False

    @pytest.mark.asyncio
    async def test_closed_on_weekend(self) -> None:
        # Friday is the Iranian weekend — the Codal window must be closed.
        with patch("jobs.market_hours._now_tehran", return_value=_FRIDAY):
            assert is_tehran_codal_window() is False

    @pytest.mark.asyncio
    async def test_open_on_saturday_workday(self) -> None:
        # Saturday IS a Tehran workday — the window must be open.
        with patch("jobs.market_hours._now_tehran", return_value=_SATURDAY):
            assert is_tehran_codal_window() is True

    @pytest.mark.asyncio
    async def test_fail_open_on_error(self) -> None:
        with patch("jobs.market_hours._now_tehran", side_effect=RuntimeError("tz broken")):
            assert is_tehran_codal_window() is True

    @pytest.mark.asyncio
    async def test_constants_are_sane(self) -> None:
        # Codal window must be strictly wider than the market window.
        assert (CODAL_OPEN_HOUR, CODAL_OPEN_MINUTE) < (MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE)
        assert (CODAL_CLOSE_HOUR, CODAL_CLOSE_MINUTE) > (MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE)
