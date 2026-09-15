"""
Tehran stock-market trading-hours helper.

BrsApi.ir free tier has a limited daily quota. Running the frequent
TSETMC/IME sync jobs around the clock burns the whole quota at night
(market closed), so by morning the API answers HTTP 402 "payment_required"
and the data never updates. These jobs should only run inside Tehran
trading hours (Sat–Wed 08:45–12:30).
"""

from __future__ import annotations

from datetime import datetime

from core.logging import get_logger

logger = get_logger(__name__)

_TEHRAN_TZ = "Asia/Tehran"
MARKET_OPEN_HOUR = 8
MARKET_OPEN_MINUTE = 45
MARKET_CLOSE_HOUR = 12
MARKET_CLOSE_MINUTE = 30
# Tehran weekend: Thursday + Friday
_WEEKEND_DAYS = {3, 4}  # Python weekday(): Mon=0 … Thu=3, Fri=4

# Codal announcements are usually published AFTER the trading session
# (afternoon), so the Codal jobs use a wider office-hours window instead
# of the narrow market window — still closed at night/weekend to save the
# free BrsApi daily quota.
CODAL_OPEN_HOUR = 8
CODAL_OPEN_MINUTE = 0
CODAL_CLOSE_HOUR = 18
CODAL_CLOSE_MINUTE = 0


def _now_tehran() -> datetime:
    """Return the current wall-clock time in Tehran (fail-open on errors)."""
    import pytz

    return datetime.now(pytz.timezone(_TEHRAN_TZ))


def _in_window(now: datetime, open_hour: int, open_minute: int, close_hour: int, close_minute: int) -> bool:
    """True when ``now`` (Tehran wall-clock) falls inside the window on a workday."""
    if now.weekday() in _WEEKEND_DAYS:
        return False
    open_dt = now.replace(hour=open_hour, minute=open_minute, second=0, microsecond=0)
    close_dt = now.replace(hour=close_hour, minute=close_minute, second=0, microsecond=0)
    return open_dt <= now <= close_dt


def is_tehran_market_open() -> bool:
    """True when Tehran stock market is inside trading hours.

    Trading hours: Saturday–Wednesday 08:45–12:30 (Asia/Tehran).
    Thursday & Friday (Iranian weekend) are always closed.

    On timezone/lookup errors it returns True (fail-open) so a tz
    problem never blocks data synchronisation.
    """
    try:
        return _in_window(
            _now_tehran(),
            MARKET_OPEN_HOUR,
            MARKET_OPEN_MINUTE,
            MARKET_CLOSE_HOUR,
            MARKET_CLOSE_MINUTE,
        )
    except Exception:  # noqa: BLE001 — never block sync on tz errors
        logger.warning("Market-hours check failed; allowing sync", exc_info=True)
        return True


def is_tehran_codal_window() -> bool:
    """True inside the wider Codal office-hours window (Sat–Wed 08:00–18:00).

    Codal announcements are published throughout the working day, mostly
    after the trading session — the wider window keeps them fresh without
    burning the free API quota at night/weekend.
    """
    try:
        return _in_window(
            _now_tehran(),
            CODAL_OPEN_HOUR,
            CODAL_OPEN_MINUTE,
            CODAL_CLOSE_HOUR,
            CODAL_CLOSE_MINUTE,
        )
    except Exception:  # noqa: BLE001 — never block sync on tz errors
        logger.warning("Codal-hours check failed; allowing sync", exc_info=True)
        return True
