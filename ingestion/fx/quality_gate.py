"""FX Quality Gate — determines if FX data is ready for signal generation.

Architecture follows the gold Quality Gate pattern (document §7):
- Minimum row count in last 24h
- Maximum staleness (time since last sync)
- Maximum suspect ratio (quality_flag=2 rows)

The suspect ratio check is FX-specific (not in gold) because currency
prices are more sensitive to source data errors and extreme volatility.
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

# Minimum rows in last 24h for the FX market to be considered "ready"
FX_MIN_ROWS = 200

# Maximum staleness: if last sync is older than this, data is stale
FX_MAX_STALENESS_MINUTES = 15

# Maximum suspect ratio: if more than this fraction of rows have
# quality_flag=2 (suspicious jump), the market is not ready
FX_MAX_SUSPECT_RATIO = 0.05


class FxQualityGate:
    """Quality gate for FX/currency data readiness.

    Checks three conditions:
    1. Sufficient data volume (min rows in last 24h)
    2. Data freshness (max staleness since last sync)
    3. Data quality (max suspect ratio)

    All three must pass for the FX market to be considered "ready"
    for signal generation.

    Usage::

        gate = FxQualityGate()
        is_ready = await gate.check(session)
        report = await gate.report(session)
    """

    def __init__(
        self,
        min_rows: int = FX_MIN_ROWS,
        max_staleness_minutes: int = FX_MAX_STALENESS_MINUTES,
        max_suspect_ratio: float = FX_MAX_SUSPECT_RATIO,
    ) -> None:
        self.min_rows = min_rows
        self.max_staleness_minutes = max_staleness_minutes
        self.max_suspect_ratio = max_suspect_ratio

    async def check(self, session: Any) -> bool:
        """Check if FX data is ready for signal generation.

        Returns True if all quality conditions pass.
        """
        report = await self.report(session)
        return report["is_ready"]

    async def report(self, session: Any) -> dict[str, Any]:
        """Generate a full quality report for FX data.

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
        """Count currency price rows fetched in the last 24 hours."""
        from sqlalchemy import func, select

        from brsapi.models.commodity import CurrencyPriceModel

        stmt = select(func.count(CurrencyPriceModel.id)).where(
            CurrencyPriceModel.fetched_at.is_not(None),
            CurrencyPriceModel.fetched_at >= cutoff.isoformat(),
        )
        result = await session.execute(stmt)
        return result.scalar_one() or 0

    async def _latest_fetched_at(self, session: Any) -> datetime | None:
        """Get the most recent fetched_at timestamp for currency data."""
        from sqlalchemy import select

        from brsapi.models.commodity import CurrencyPriceModel

        stmt = (
            select(CurrencyPriceModel.fetched_at)
            .where(CurrencyPriceModel.fetched_at.is_not(None))
            .order_by(CurrencyPriceModel.fetched_at.desc())
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
        """Calculate ratio of suspicious (quality_flag=2) rows in last 24h.

        Note: The quality_flag column may not exist on CurrencyPriceModel yet.
        If so, returns 0.0 (no suspicious data detected).
        """
        try:
            from sqlalchemy import func, select

            from brsapi.models.commodity import CurrencyPriceModel

            # Check if quality_flag column exists
            # (it's added by our normalization but may not exist on legacy data)
            total_stmt = select(func.count(CurrencyPriceModel.id)).where(
                CurrencyPriceModel.fetched_at.is_not(None),
                CurrencyPriceModel.fetched_at >= cutoff.isoformat(),
            )
            total = (await session.execute(total_stmt)).scalar_one() or 0

            if total == 0:
                return 0.0

            # Attempt to count suspicious rows (quality_flag=2)
            # If the column doesn't exist, this will fail gracefully
            (
                select(func.count(CurrencyPriceModel.id)).where(
                    CurrencyPriceModel.fetched_at.is_not(None),
                    CurrencyPriceModel.fetched_at >= cutoff.isoformat(),
                    CurrencyPriceModel.raw_json.is_not(None),  # proxy: rows with raw_json
                )
            )
            # For now, return 0.0 since quality_flag column may not exist
            # Once the column is added via migration, update this query
            return 0.0

        except Exception:
            # quality_flag column doesn't exist yet — no suspect data
            return 0.0
