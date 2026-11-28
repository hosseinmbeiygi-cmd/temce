"""Regression tests for audit finding F8 — future timestamps must not count as fresh
(ممیزی 2026-11-28).

Fixed: ``services.alert_engine.data.freshness`` now returns ``invalid`` when the
source timestamp runs more than ``FUTURE_TOLERANCE_SECONDS`` (60s) ahead of "now".
Previously a negative age was silently accepted as ``valid`` — a broken provider
clock would make stale/fabricated data look live.

Downstream this fails closed: an ``invalid`` quote blocks the decision
(``decision.USABLE`` does not include it) and an ``invalid`` mark leaves a position
unmarked (``risk`` only trusts valid/last_session).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from services.alert_engine.data import freshness

NOW = datetime(2026, 11, 28, 8, 0, tzinfo=UTC)


def test_future_beyond_tolerance_is_invalid():
    as_of = NOW + timedelta(hours=1)
    assert freshness(as_of, now=NOW, market_open=True, open_seconds=300, closed_hours=100) == "invalid"
    assert freshness(as_of, now=NOW, market_open=False, open_seconds=300, closed_hours=100) == "invalid"


def test_small_clock_skew_still_valid():
    """A source a few seconds ahead is tolerated as normal clock skew."""
    as_of = NOW + timedelta(seconds=30)
    assert freshness(as_of, now=NOW, market_open=True, open_seconds=300, closed_hours=100) == "valid"


def test_exact_tolerance_boundary():
    """age == -60s is exactly at the tolerance → still accepted (strictly beyond it is invalid)."""
    as_of = NOW + timedelta(seconds=60)
    assert freshness(as_of, now=NOW, market_open=True, open_seconds=300, closed_hours=100) == "valid"


def test_past_ages_unchanged():
    """The fix must not alter the established past-age semantics."""
    assert freshness(NOW - timedelta(seconds=180), now=NOW, market_open=True,
                     open_seconds=300, closed_hours=100) == "valid"
    assert freshness(NOW - timedelta(seconds=600), now=NOW, market_open=True,
                     open_seconds=300, closed_hours=100) == "stale"
    assert freshness(NOW - timedelta(hours=20), now=NOW, market_open=False,
                     open_seconds=300, closed_hours=100) == "last_session"
    assert freshness(NOW - timedelta(hours=120), now=NOW, market_open=False,
                     open_seconds=300, closed_hours=100) == "stale"


def test_missing_stays_missing():
    assert freshness(None, now=NOW, market_open=True, open_seconds=300, closed_hours=100) == "missing"
