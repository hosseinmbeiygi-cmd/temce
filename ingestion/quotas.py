"""BrsApi quota governance for the ingestion scope.

Reuse-first: the platform already owns a shared, Redis-backed request budget
in :class:`brsapi.budget.BrsApiBudgetGovernor` (persistent daily counter,
sliding 5-minute window and the HTTP-302 cooldown).  This module does **not**
create a second counter.  It:

1. declares the ingestion plan profile (300 req / 5 min, 10,000 req / day),
2. builds a limiter/governor pair seeded with that profile, and
3. exposes a read-only :class:`IngestionQuotaTracker` so callers can inspect
   headroom and fail fast before spending a request.

``contracts/events.md`` defines no ingestion event yet, so nothing here
publishes invented events.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30))

# ``brsapi.config.BrsApiSettings`` reads these from .env (pydantic-settings).
DAILY_LIMIT_ENV = "BRSAPI_GLOBAL_DAILY_LIMIT"
FIVE_MIN_LIMIT_ENV = "BRSAPI_GLOBAL_5MIN_LIMIT"


class QuotaExceededError(RuntimeError):
    """Raised when the ingestion scope has no BrsApi headroom left."""


@dataclass(frozen=True)
class QuotaProfile:
    """Declared BrsApi account limits used by a single scope."""

    daily_limit: int
    five_min_limit: int
    label: str = "ingestion"

    def __post_init__(self) -> None:
        if self.daily_limit <= 0:
            raise ValueError("daily_limit must be positive")
        if self.five_min_limit <= 0:
            raise ValueError("five_min_limit must be positive")
        if self.five_min_limit > self.daily_limit:
            raise ValueError("five_min_limit cannot exceed daily_limit")

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "daily_limit": self.daily_limit,
            "five_min_limit": self.five_min_limit,
        }


# 30s AllSymbols cadence during market hours = 10 req / 5 min = ~2,880 req/day,
# comfortably inside this profile.  300/5min leaves headroom for the rest of
# the platform on the same key; 10,000/day matches the documented plan cap.
INGESTION_QUOTA_PROFILE = QuotaProfile(
    daily_limit=10_000,
    five_min_limit=300,
    label="ingestion",
)
DEFAULT_QUOTA_PROFILE = INGESTION_QUOTA_PROFILE

# Conservative default that keeps the key far below the real plan cap.  Used
# as the reference when nobody overrides the plan profile.
CONSERVATIVE_QUOTA_PROFILE = QuotaProfile(
    daily_limit=4_000,
    five_min_limit=1_000,
    label="platform-default",
)


@dataclass(frozen=True)
class QuotaSnapshot:
    """Point-in-time view of the shared BrsApi budget."""

    profile: QuotaProfile
    backend: str
    daily_used: int
    daily_limit: int
    five_min_used: int
    five_min_limit: int
    blocked: bool
    blocked_until: str | None = None

    @property
    def daily_remaining(self) -> int:
        return max(0, self.daily_limit - self.daily_used)

    @property
    def five_min_remaining(self) -> int:
        return max(0, self.five_min_limit - self.five_min_used)

    @property
    def daily_used_pct(self) -> float:
        return round(self.daily_used / self.daily_limit * 100, 1) if self.daily_limit else 0.0

    @property
    def exhausted(self) -> bool:
        return self.daily_remaining <= 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile.as_dict(),
            "backend": self.backend,
            "daily_used": self.daily_used,
            "daily_limit": self.daily_limit,
            "daily_remaining": self.daily_remaining,
            "daily_used_pct": self.daily_used_pct,
            "five_min_used": self.five_min_used,
            "five_min_limit": self.five_min_limit,
            "five_min_remaining": self.five_min_remaining,
            "blocked": self.blocked,
            "blocked_until": self.blocked_until,
            "exhausted": self.exhausted,
        }

    @classmethod
    def from_governor_stats(
        cls,
        stats: dict[str, Any],
        profile: QuotaProfile,
    ) -> QuotaSnapshot:
        """Build a snapshot from ``BrsApiBudgetGovernor.stats()`` output."""
        global_stats = stats.get("global", {}) or {}
        block = stats.get("block", {}) or {}
        governor = stats.get("governor", {}) or {}
        return cls(
            profile=profile,
            backend=str(governor.get("backend", "none")),
            daily_used=int(global_stats.get("daily_count", 0) or 0),
            daily_limit=int(global_stats.get("daily_limit", profile.daily_limit) or profile.daily_limit),
            five_min_used=int(global_stats.get("5min_count", 0) or 0),
            five_min_limit=int(global_stats.get("5min_limit", profile.five_min_limit) or profile.five_min_limit),
            blocked=bool(block.get("blocked", False)),
            blocked_until=block.get("blocked_until"),
        )


@dataclass(frozen=True)
class QuotaAssessment:
    """Result of comparing the active settings against the wanted profile."""

    expected: QuotaProfile
    active_daily_limit: int
    active_five_min_limit: int
    matched: bool
    drift: tuple[str, ...] = ()

    @property
    def recommended_env(self) -> dict[str, str]:
        """Env vars that make the whole platform use the expected profile."""
        return {
            DAILY_LIMIT_ENV: str(self.expected.daily_limit),
            FIVE_MIN_LIMIT_ENV: str(self.expected.five_min_limit),
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "expected": self.expected.as_dict(),
            "active_daily_limit": self.active_daily_limit,
            "active_five_min_limit": self.active_five_min_limit,
            "matched": self.matched,
            "drift": list(self.drift),
            "recommended_env": self.recommended_env,
        }


def assess_active_profile(profile: QuotaProfile = DEFAULT_QUOTA_PROFILE) -> QuotaAssessment:
    """Compare ``brsapi.config.settings`` limits with ``profile``.

    The shared governor is scoped to the platform, so the honest fix for a
    mismatch is an ``.env`` change (reported via ``recommended_env``) rather
    than silently re-keying the counters from one module.
    """
    from brsapi.config import settings as brsapi_settings

    active_daily = int(getattr(brsapi_settings, "global_daily_limit", 0) or 0)
    active_five_min = int(getattr(brsapi_settings, "global_5min_limit", 0) or 0)

    drift: list[str] = []
    if active_daily != profile.daily_limit:
        drift.append(f"{DAILY_LIMIT_ENV}: active={active_daily} expected={profile.daily_limit}")
    if active_five_min != profile.five_min_limit:
        drift.append(f"{FIVE_MIN_LIMIT_ENV}: active={active_five_min} expected={profile.five_min_limit}")

    return QuotaAssessment(
        expected=profile,
        active_daily_limit=active_daily,
        active_five_min_limit=active_five_min,
        matched=not drift,
        drift=tuple(drift),
    )


def build_ingestion_limiter(profile: QuotaProfile = DEFAULT_QUOTA_PROFILE) -> Any:
    """Create a limiter enforcing the ingestion profile."""
    from brsapi.rate_limiter import RateLimiter

    return RateLimiter(
        daily_limit=profile.daily_limit,
        five_min_limit=profile.five_min_limit,
    )


def build_ingestion_governor(
    profile: QuotaProfile = DEFAULT_QUOTA_PROFILE,
    *,
    limiter: Any | None = None,
    redis_client: Any | None = None,
    persist: bool = True,
) -> Any:
    """Create a persistent governor enforcing the ingestion profile.

    ``persist=True`` keeps the Redis/file-backed counters, so a process
    restart (or a second replica) never gets a fresh budget.
    """
    from brsapi.budget import BrsApiBudgetGovernor

    active_limiter = limiter or build_ingestion_limiter(profile)
    return BrsApiBudgetGovernor(
        rate_limiter=active_limiter,
        daily_limit=profile.daily_limit,
        five_min_limit=profile.five_min_limit,
        redis_client=redis_client,
        persist=persist,
    )


class IngestionQuotaTracker:
    """Read-only budget view plus fail-fast headroom checks.

    Wraps the shared governor so callers never touch private limiter state.
    """

    def __init__(
        self,
        governor: Any | None = None,
        *,
        profile: QuotaProfile = DEFAULT_QUOTA_PROFILE,
    ) -> None:
        if governor is None:
            from brsapi.budget import get_budget_governor

            governor = get_budget_governor()
        self._governor = governor
        self._profile = profile

    @property
    def profile(self) -> QuotaProfile:
        return self._profile

    async def snapshot(self) -> QuotaSnapshot:
        stats = await self._governor.stats()
        return QuotaSnapshot.from_governor_stats(stats, self._profile)

    async def has_headroom(self, tokens: int = 1) -> bool:
        """True when ``tokens`` requests can be spent right now."""
        snapshot = await self.snapshot()
        return not snapshot.blocked and snapshot.daily_remaining >= max(1, tokens)

    async def ensure_headroom(self, tokens: int = 1) -> QuotaSnapshot:
        """Return a snapshot, raising when a request must not be attempted."""
        snapshot = await self.snapshot()
        if snapshot.blocked:
            raise QuotaExceededError(
                f"BrsApi key is in the 302 cooldown until {snapshot.blocked_until}"
            )
        if snapshot.daily_remaining < max(1, tokens):
            raise QuotaExceededError(
                f"BrsApi daily budget exhausted ({snapshot.daily_used}/{snapshot.daily_limit})"
            )
        return snapshot

    async def record_block(self, location: str = "") -> None:
        """Forward an HTTP 302 signal to the shared governor."""
        await self._governor.report_302(location)

    def assessment(self) -> QuotaAssessment:
        return assess_active_profile(self._profile)
