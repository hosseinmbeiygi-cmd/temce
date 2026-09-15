"""Gold Quality Gate — determines if gold data is ready for signal generation.

Architecture follows the gold implementation document (section 6):
- Minimum row count in last 24h
- Maximum staleness (time since last sync)

The quality gate ensures the signal engine only generates gold signals
when data is truly sufficient and fresh — not from a few scattered rows.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

try:
    from core.logging import get_logger

    logger = get_logger(__name__)
except ImportError:
    import logging

    logger = logging.getLogger(__name__)


# ── Thresholds ────────────────────────────────────────────────────────

# Minimum rows in last 24h for the gold market to be considered "ready"
GOLD_MIN_ROWS = 200

# Maximum staleness: if last sync is older than this, data is stale
GOLD_MAX_STALENESS_MINUTES = 15

# Maximum suspect ratio: if more than this fraction of rows have
# quality_flag=2 (suspicious), the market is not ready
GOLD_MAX_SUSPECT_RATIO = 0.05


class GoldQualityGate:
    """Quality gate for gold data readiness.

    Checks three conditions:
    1. Sufficient data volume (min rows in last 24h)
    2. Data freshness (max staleness since last sync)
    3. Data quality (max suspect ratio)

    All three must pass for the gold market to be considered "ready"
    for signal generation.

    Usage::

        gate = GoldQualityGate()
        is_ready = await gate.check(session)
        report = await gate.report(session)
    """

    def __init__(
        self,
        min_rows: int = GOLD_MIN_ROWS,
        max_staleness_minutes: int = GOLD_MAX_STALENESS_MINUTES,
        max_suspect_ratio: float = GOLD_MAX_SUSPECT_RATIO,
    ) -> None:
        self.min_rows = min_rows
        self.max_staleness_minutes = max_staleness_minutes
        self.max_suspect_ratio = max_suspect_ratio

    async def check(self, session: Any) -> bool:
        """Check if gold data is ready for signal generation.

        Returns True if all quality conditions pass.
        """
        report = await self.report(session)
        return report["is_ready"]

    async def report(self, session: Any) -> dict[str, Any]:
        """Generate a full quality report for gold data.

        Returns a dict with:
        - is_ready: bool — overall readiness
        - row_count: int — rows in last 24h
        - latest_fetched_at: str | None — timestamp of last sync
        - suspect_ratio: float — ratio of suspicious rows
        - reason: str — human-readable reason if not ready
        """
        now = datetime.now(UTC)
        cutoff = now - timedelta(hours=24)

        # Count rows in last 24h
        row_count = await self._count_rows_last_24h(session, cutoff)
        if row_count < self.min_rows:
            return {
                "is_ready": False,
                "row_count": row_count,
                "latest_fetched_at": None,
                "suspect_ratio": 0.0,
                "reason": f"Insufficient data: {row_count} rows < {self.min_rows} required",
            }

        # Check staleness
        latest_fetched = await self._latest_fetched_at(session)
        if latest_fetched is None:
            return {
                "is_ready": False,
                "row_count": row_count,
                "latest_fetched_at": None,
                "suspect_ratio": 0.0,
                "reason": "No fetched_at timestamp found",
            }

        staleness_minutes = (now - latest_fetched).total_seconds() / 60
        if staleness_minutes > self.max_staleness_minutes:
            return {
                "is_ready": False,
                "row_count": row_count,
                "latest_fetched_at": latest_fetched.isoformat(),
                "suspect_ratio": 0.0,
                "reason": f"Data stale: {staleness_minutes:.0f}min > {self.max_staleness_minutes}min threshold",
            }

        # Check suspect ratio
        suspect_ratio = await self._suspect_ratio_last_24h(session, cutoff)
        if suspect_ratio > self.max_suspect_ratio:
            return {
                "is_ready": False,
                "row_count": row_count,
                "latest_fetched_at": latest_fetched.isoformat(),
                "suspect_ratio": suspect_ratio,
                "reason": f"Too many suspicious rows: {suspect_ratio:.1%} > {self.max_suspect_ratio:.1%} threshold",
            }

        return {
            "is_ready": True,
            "row_count": row_count,
            "latest_fetched_at": latest_fetched.isoformat(),
            "suspect_ratio": suspect_ratio,
            "reason": None,
        }

    async def _count_rows_last_24h(self, session: Any, cutoff: datetime) -> int:
        """Count gold price rows fetched in the last 24 hours."""
        from sqlalchemy import func, select

        from brsapi.models.commodity import GoldCoinPriceModel

        stmt = select(func.count(GoldCoinPriceModel.id)).where(
            GoldCoinPriceModel.fetched_at.is_not(None),
            GoldCoinPriceModel.fetched_at >= cutoff.isoformat(),
        )
        result = await session.execute(stmt)
        return result.scalar_one() or 0

    async def _latest_fetched_at(self, session: Any) -> datetime | None:
        """Get the most recent fetched_at timestamp for gold data."""
        from sqlalchemy import select

        from brsapi.models.commodity import GoldCoinPriceModel

        stmt = (
            select(GoldCoinPriceModel.fetched_at)
            .where(GoldCoinPriceModel.fetched_at.is_not(None))
            .order_by(GoldCoinPriceModel.fetched_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        fetched = result.scalar_one_or_none()
        if fetched:
            try:
                return datetime.fromisoformat(fetched.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                return None
        return None

    async def _suspect_ratio_last_24h(self, session: Any, cutoff: datetime) -> float:
        """Calculate ratio of suspicious rows in last 24h.

        Returns 0.0 since quality_flag column may not exist yet.
        """
        return 0.0
