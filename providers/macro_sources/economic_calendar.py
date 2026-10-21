"""Economic calendar source interface + seeded (schedule-only) implementation.

The calendar itself is a schedule (CPI / NFP / FOMC dates), not a live quote
feed.  The seeded provider loads known high-volatility event dates so the
``gold_economic_calendar_events`` table can be populated idempotently without
any external network call.  Subclass ``EconomicCalendarProvider`` to wire a
real feed later when one is available.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

# ── Verified seed schedule (STEP 6-FIX-2) ────────────────────────────────
# CPI release dates — source: U.S. Bureau of Labor Statistics,
#   "Schedule of Releases for the Consumer Price Index"
#   https://www.bls.gov/schedule/news_release/cpi.htm
#   (Reference month → release date: Oct-2026 → 2026-11-10; Nov-2026 →
#   2026-12-10; Dec-2026 → 2027-01-13; Jan-2027 → 2027-02-11; Feb-2027 →
#   2027-03-10; Mar-2027 → 2027-04-13; Apr-2027 → 2027-05-12; May-2027 →
#   2027-06-10; Jun-2027 → 2027-07-14 (seeded: covers "at least 2027-06-30").
#
# NFP / Employment Situation release dates — source: U.S. Bureau of Labor
#   Statistics, "Schedule of Releases for the Employment Situation"
#   https://www.bls.gov/schedule/news_release/empsit.htm
#   (Oct-2026 → 2026-11-06; Nov-2026 → 2026-12-04; Dec-2026 → 2027-01-08;
#   Jan-2027 → 2027-02-05; Feb-2027 → 2027-03-05; Mar-2027 → 2027-04-02;
#   Apr-2027 → 2027-05-07; May-2027 → 2027-06-04; Jun-2027 → 2027-07-02
#   (seeded: covers "at least 2027-06-30").
#
# FOMC statement dates (2nd day of each 2-day meeting) — source: Board of
#   Governors of the Federal Reserve System,
#   tentative meeting schedule for 2026 and 2026-2027 press releases:
#   https://www.federalreserve.gov/newsevents/pressreleases/monetary20240809a.htm
#   (Jan 27-28 2026; Mar 17-18; Apr 28-29; Jun 16-17; Jul 28-29;
#   Sep 15-16; Oct 27-28; Dec 8-9),
#   https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
#   (2027: Jan 26-27; Mar 16-17; Apr 27-28; Jun 8-9).
#   Only statement dates in [2026-10-19, 2027-06-30] are seeded below.
#
# MISSING (could not be verified from an official page, so NOT seeded):
#   - September-2026 CPI release date (released ~Oct 2026; not listed on the
#     current BLS CPI schedule page, which starts at Oct-2026 ref month).
#   - September-2026 Employment Situation release date (released ~Oct 2026;
#     not listed on the current BLS empsit schedule page).
#   - Any BLS/BEA release not on the two BLS schedule pages above
#     (e.g. no BEA series was seeded — no BEA schedule was consulted).
#   Per instructions these are left out, not guessed.

_SEEDED_CPI_DATES: tuple[str, ...] = (
    "2026-11-10",  # CPI, ref Oct-2026 (BLS CPI schedule)
    "2026-12-10",  # CPI, ref Nov-2026
    "2027-01-13",  # CPI, ref Dec-2026
    "2027-02-11",  # CPI, ref Jan-2027
    "2027-03-10",  # CPI, ref Feb-2027
    "2027-04-13",  # CPI, ref Mar-2027
    "2027-05-12",  # CPI, ref Apr-2027
    "2027-06-10",  # CPI, ref May-2027
    "2027-07-14",  # CPI, ref Jun-2027 (extends coverage past 2027-06-30)
)

_SEEDED_NFP_DATES: tuple[str, ...] = (
    "2026-11-06",  # Employment Situation, ref Oct-2026 (BLS empsit schedule)
    "2026-12-04",  # ref Nov-2026
    "2027-01-08",  # ref Dec-2026
    "2027-02-05",  # ref Jan-2027
    "2027-03-05",  # ref Feb-2027
    "2027-04-02",  # ref Mar-2027
    "2027-05-07",  # ref Apr-2027
    "2027-06-04",  # ref May-2027
    "2027-07-02",  # ref Jun-2027 (extends coverage past 2027-06-30)
)

_SEEDED_FOMC_DATES: tuple[str, ...] = (
    "2026-10-28",  # FOMC statement, meeting Oct 27-28 2026 (Fed schedule)
    "2026-12-09",  # meeting Dec 8-9 2026
    "2027-01-27",  # meeting Jan 26-27 2027
    "2027-03-17",  # meeting Mar 16-17 2027
    "2027-04-28",  # meeting Apr 27-28 2027
    "2027-06-09",  # meeting Jun 8-9 2027
)


def _build_default_seed_events() -> list[dict[str, Any]]:
    """Build the default verified seed list (CPI + NFP + FOMC only)."""
    events: list[dict[str, Any]] = []
    for d in _SEEDED_CPI_DATES:
        ref = d[:7]
        events.append(
            {
                "event_id": f"seed-cpi-{d}",
                "event_date": d,
                "event_time": "08:30",
                "title": f"US CPI ({ref} reference month)",
                "country": "US",
                "category": "CPI",
                "importance": 3,
                "is_high_volatility": True,
                "source": "BLS schedule (https://www.bls.gov/schedule/news_release/cpi.htm)",
            }
        )
    for d in _SEEDED_NFP_DATES:
        events.append(
            {
                "event_id": f"seed-nfp-{d}",
                "event_date": d,
                "event_time": "08:30",
                "title": "US Employment Situation (NFP)",
                "country": "US",
                "category": "NFP",
                "importance": 3,
                "is_high_volatility": True,
                "source": "BLS schedule (https://www.bls.gov/schedule/news_release/empsit.htm)",
            }
        )
    for d in _SEEDED_FOMC_DATES:
        events.append(
            {
                "event_id": f"seed-fomc-{d}",
                "event_date": d,
                "event_time": "14:00",
                "title": "FOMC statement",
                "country": "US",
                "category": "FOMC",
                "importance": 3,
                "is_high_volatility": True,
                "source": "Federal Reserve (https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm)",
            }
        )
    return events


DEFAULT_SEED_EVENTS: list[dict[str, Any]] = _build_default_seed_events()


class EconomicCalendarProvider(ABC):
    """Source of scheduled economic events."""

    name: str = "economic_calendar"

    @abstractmethod
    def fetch(self) -> list[dict[str, Any]]:
        """Return scheduled events as dicts.

        Each dict: ``event_id``, ``event_date`` (date|str), ``event_time``,
        ``title``, ``country``, ``category`` (e.g. CPI / NFP / FOMC),
        ``importance`` (1-3), ``is_high_volatility`` (bool), ``source``.
        """


class SeededEconomicCalendarProvider(EconomicCalendarProvider):
    """Populate the calendar from a known schedule (no network).

    CPI / NFP / FOMC dates are flagged high-volatility; everything else is
    normal.  Window flags (``is_high_vol_window``) are computed separately
    against the populated table.
    """

    name = "economic_calendar:seeded"

    def __init__(self, events: list[dict[str, Any]] | None = None) -> None:
        # Default: verified CPI/NFP/FOMC seed (no network). Explicit [] opts out.
        self._events = list(events) if events is not None else list(DEFAULT_SEED_EVENTS)

    def fetch(self) -> list[dict[str, Any]]:
        return list(self._events)
