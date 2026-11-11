"""Market dates are stamped in Tehran time, not the host's timezone.

Iran is UTC+3:30. A UTC host is still on the previous calendar day between
20:30 UTC and midnight, which is exactly when “today's” NAV dedupe and the
intraday-candle stamp run late enough to matter. ``jdatetime.date.today()``
reads the host clock, so both used to be able to land one session early.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import jdatetime
import pytest

import core.time as core_time
from brsapi.parsers import TsetmcParser

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _jalali(d: date) -> str:
    return jdatetime.date.fromgregorian(date=d).strftime("%Y-%m-%d")


def test_tehran_date_is_used_at_the_utc_boundary(monkeypatch) -> None:
    # 2026-10-29 21:00 UTC == 2026-10-30 00:30 Tehran.
    fixed = datetime(2026, 10, 29, 21, 0, tzinfo=UTC)
    monkeypatch.setattr(core_time, "now_tehran", lambda: fixed.astimezone(core_time.IRAN_TZ))

    assert core_time.today_jalali_tehran() == _jalali(date(2026, 10, 30))
    assert core_time.today_jalali_tehran() != _jalali(fixed.date())


def test_intraday_candles_are_stamped_with_tehran_today(monkeypatch) -> None:
    import brsapi.parsers.tsetmc as tsetmc_module

    monkeypatch.setattr(tsetmc_module, "today_jalali_tehran", lambda: "1405-08-08")

    (row,) = TsetmcParser.parse_candlesticks(
        {"candle_intraday": [{"time": "09:02", "open": 1, "close": 2}]}
    )

    assert row["date"] == "1405-08-08"
    assert row["shamsi_date"] == "1405-08-08"


@pytest.mark.parametrize(
    "relative",
    ["brsapi/parsers/tsetmc.py", "brsapi/services/sync_service.py"],
)
def test_market_write_paths_do_not_read_the_host_clock(relative: str) -> None:
    """Guard: these modules stamp market dates; ``date.today()`` would drift."""
    source = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
    assert "jdatetime.date.today()" not in source
    assert "date.today()" not in source
