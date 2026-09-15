"""Tests for the ingestion quota/budget layer (no network, no Redis)."""

from __future__ import annotations

import pytest

from ingestion.quotas import (
    DAILY_LIMIT_ENV,
    FIVE_MIN_LIMIT_ENV,
    INGESTION_QUOTA_PROFILE,
    IngestionQuotaTracker,
    QuotaExceededError,
    QuotaProfile,
    QuotaSnapshot,
    assess_active_profile,
)


class FakeGovernor:
    def __init__(self, stats: dict) -> None:
        self._stats = stats
        self.block_locations: list[str] = []

    async def stats(self) -> dict:
        return self._stats

    async def report_302(self, location: str = "") -> None:
        self.block_locations.append(location)


def _stats(*, used: int = 100, blocked: bool = False) -> dict:
    return {
        "governor": {"backend": "redis", "initialized": True},
        "global": {
            "daily_count": used,
            "daily_limit": 10_000,
            "daily_remaining": max(0, 10_000 - used),
            "5min_count": 5,
            "5min_limit": 300,
        },
        "block": {"blocked": blocked, "blocked_until": "2026-09-12T14:00:00+03:30"},
    }


def test_profile_rejects_invalid_limits() -> None:
    with pytest.raises(ValueError):
        QuotaProfile(daily_limit=0, five_min_limit=10)
    with pytest.raises(ValueError):
        QuotaProfile(daily_limit=100, five_min_limit=0)
    with pytest.raises(ValueError):
        QuotaProfile(daily_limit=100, five_min_limit=200)


def test_ingestion_profile_matches_requested_plan() -> None:
    assert INGESTION_QUOTA_PROFILE.five_min_limit == 300
    assert INGESTION_QUOTA_PROFILE.daily_limit == 10_000


def test_snapshot_math_from_governor_stats() -> None:
    snapshot = QuotaSnapshot.from_governor_stats(_stats(used=9_900), INGESTION_QUOTA_PROFILE)
    assert snapshot.daily_remaining == 100
    assert snapshot.five_min_remaining == 295
    assert snapshot.daily_used_pct == 99.0
    assert snapshot.exhausted is False
    assert snapshot.backend == "redis"


def test_snapshot_marks_exhausted() -> None:
    snapshot = QuotaSnapshot.from_governor_stats(_stats(used=10_000), INGESTION_QUOTA_PROFILE)
    assert snapshot.exhausted is True
    assert snapshot.daily_remaining == 0


async def test_tracker_has_headroom_and_ensure() -> None:
    tracker = IngestionQuotaTracker(FakeGovernor(_stats()), profile=INGESTION_QUOTA_PROFILE)
    assert await tracker.has_headroom() is True
    snapshot = await tracker.ensure_headroom()
    assert snapshot.daily_used == 100


async def test_tracker_rejects_when_exhausted() -> None:
    tracker = IngestionQuotaTracker(
        FakeGovernor(_stats(used=10_000)),
        profile=INGESTION_QUOTA_PROFILE,
    )
    assert await tracker.has_headroom() is False
    with pytest.raises(QuotaExceededError):
        await tracker.ensure_headroom()


async def test_tracker_rejects_when_blocked() -> None:
    tracker = IngestionQuotaTracker(
        FakeGovernor(_stats(blocked=True)),
        profile=INGESTION_QUOTA_PROFILE,
    )
    with pytest.raises(QuotaExceededError, match="cooldown"):
        await tracker.ensure_headroom()


async def test_tracker_forwards_block_signal() -> None:
    governor = FakeGovernor(_stats())
    tracker = IngestionQuotaTracker(governor, profile=INGESTION_QUOTA_PROFILE)
    await tracker.record_block("http://heavy/file.zip")
    assert governor.block_locations == ["http://heavy/file.zip"]


def test_assessment_reports_env_fix_for_drift() -> None:
    assessment = assess_active_profile(INGESTION_QUOTA_PROFILE)
    assert assessment.recommended_env == {
        DAILY_LIMIT_ENV: "10000",
        FIVE_MIN_LIMIT_ENV: "300",
    }
    if not assessment.matched:
        assert assessment.drift
        assert any(DAILY_LIMIT_ENV in item or FIVE_MIN_LIMIT_ENV in item for item in assessment.drift)
